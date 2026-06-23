"""C-topology ablation eval driver.

Runs each of the 5 ablation cases on each of 3 skill conditions
(seed, v8 trained, v8 + 5 negative rules), single seed, OfficeQA bench.

Outputs:
  analysis/c_topo_ablation/eval_results/<condition>/<case_id>/
    output.txt
    execution_trace_r0.md
    assessment_r0.json
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"

from bench import get_bench
from pipeline.execution import run_execute
from runners.cost_tracker import CostTracker
from runners.model_dispatch import get_client_for_model

MODEL = "gpt-5.4"
CASES = ["oqa-14", "oqa-16", "oqa-33", "oqa-40", "oqa-129"]
CONDITIONS = {
    "seed":         "seeds",
    "v8":           "results/runs/g2b-v8_gpt-5.4_oqa-gpt54-smoke/train/final_skill",
    "v8_plus_neg":  "analysis/c_topo_ablation/skill_v8_plus_neg",
}
OUTPUT_ROOT = Path("analysis/c_topo_ablation/eval_results")


async def run_one(condition: str, skill_src: Path, case_id: str, idx: int) -> dict:
    project_root = Path(".").resolve()
    out_dir = OUTPUT_ROOT / condition / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Stage skill
    skills_dir = out_dir / "_skills"
    if skills_dir.exists():
        shutil.rmtree(skills_dir)
    skills_dir.mkdir(parents=True)
    src_officeqa = skill_src / "officeqa"
    if not src_officeqa.exists():
        # seeds/officeqa
        src_officeqa = Path("seeds/officeqa")
    shutil.copytree(src_officeqa, skills_dir / "officeqa")

    bench = get_bench("officeqa", data_dir="data/benchmarks/officeqa")
    dataset = bench.load_dataset()
    dataset_idx = next(i for i, e in enumerate(dataset) if e["id"] == case_id)

    seed_data = bench.prepare_seed_data(dataset, dataset_idx, out_dir)
    cost = CostTracker(MODEL)
    sem = asyncio.Semaphore(2)
    client = get_client_for_model(MODEL)

    print(f"\n  [{condition}/{case_id}] starting...")
    exec_result = await run_execute(
        seed_data=seed_data,
        semaphore=sem,
        skills_dir=skills_dir,
        model=MODEL,
        project_root=project_root,
        max_turns=30,
        round_num=0,
        cost_tracker=cost,
        openai_client=client,
        skill_name="officeqa",
    )
    assessment = bench.assess(seed_data, exec_result, round_num=0)

    # Move/copy artifacts to predictable location
    src_workdir = Path(seed_data["task_workdir"])
    for fname in ["output.txt", f"execution_trace_r0.md", f"assessment_r0.json", f"exec_r0.jsonl"]:
        sp = src_workdir / fname
        dp = out_dir / fname
        if sp.exists():
            shutil.copy2(sp, dp)

    is_correct = assessment["is_correct"]
    print(f"  [{condition}/{case_id}] PASS={is_correct} cost=${cost.total_cost:.3f}")
    return {
        "condition": condition,
        "case_id": case_id,
        "is_correct": is_correct,
        "cost": cost.total_cost,
        "elapsed": assessment["elapsed"],
    }


async def main_async():
    results = []
    for condition, skill_path in CONDITIONS.items():
        skill_src = Path(skill_path)
        for idx, case_id in enumerate(CASES):
            try:
                r = await run_one(condition, skill_src, case_id, idx)
                results.append(r)
            except Exception as e:
                print(f"  [{condition}/{case_id}] ERROR: {e}")
                results.append({"condition": condition, "case_id": case_id, "error": str(e)})

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "summary.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSummary written to {OUTPUT_ROOT / 'summary.json'}")

    # Quick tally
    print("\n=== outcome_pass tally ===")
    print(f"{'condition':<14} pass / 5")
    for cond in CONDITIONS:
        n = sum(1 for r in results if r.get("condition") == cond and r.get("is_correct"))
        print(f"  {cond:<14} {n}/5")


if __name__ == "__main__":
    asyncio.run(main_async())
