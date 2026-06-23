"""C-topo v2 main eval: v8+neg condition × N stable_fail cases × 5 seeds.

The v8 (control) data already exists in pilot/branch2/branch3 outputs
per-case, so we ONLY run v8+neg here. Saves 5×N runs.

Inputs:
- analysis/c_topo_ablation/v2_main_pool.json (selected stable_fail cases + skill path)
- analysis/c_topo_ablation/v2_rules.yaml (the rules appended to v8 skill)

Outputs:
- analysis/c_topo_ablation/v2_main/{case}_s{seed}/
- analysis/c_topo_ablation/v2_main/main_results.json
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
N_SEEDS = 5
SKILL_DIR = Path("analysis/c_topo_ablation/v2_skill_v8_plus_neg")  # built by build_skill_v2.py
POOL_PATH = Path("analysis/c_topo_ablation/v2_main_pool.json")
OUTPUT_ROOT = Path("analysis/c_topo_ablation/v2_main")


async def run_one(case_id: str, seed_idx: int) -> dict:
    project_root = Path(".").resolve()
    out_dir = OUTPUT_ROOT / f"{case_id}_s{seed_idx}"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    skills_dir = out_dir / "_skills"
    skills_dir.mkdir(parents=True)
    shutil.copytree(SKILL_DIR / "officeqa", skills_dir / "officeqa")

    bench = get_bench("officeqa", data_dir="data/benchmarks/officeqa")
    dataset = bench.load_dataset()
    dataset_idx = next(i for i, e in enumerate(dataset) if e["id"] == case_id)
    seed_data = bench.prepare_seed_data(dataset, dataset_idx, out_dir)

    cost = CostTracker(MODEL)
    sem = asyncio.Semaphore(2)
    client = get_client_for_model(MODEL)

    print(f"  [{case_id}/seed{seed_idx}] starting...")
    exec_result = await run_execute(
        seed_data=seed_data, semaphore=sem, skills_dir=skills_dir,
        model=MODEL, project_root=project_root, max_turns=30, round_num=0,
        cost_tracker=cost, openai_client=client, skill_name="officeqa",
    )
    assessment = bench.assess(seed_data, exec_result, round_num=0)

    src = Path(seed_data["task_workdir"])
    for fname in ["output.txt", "execution_trace_r0.md", "assessment_r0.json"]:
        if (src/fname).exists(): shutil.copy2(src/fname, out_dir/fname)

    return {
        "case_id": case_id, "seed_idx": seed_idx,
        "is_correct": assessment["is_correct"],
        "cost": cost.total_cost, "elapsed": assessment["elapsed"],
        "condition": "v8_plus_neg",
    }


async def main_async():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    pool = json.loads(POOL_PATH.read_text())
    cases = pool["main_eval_cases"]

    print(f"Main eval: {len(cases)} cases × {N_SEEDS} seeds = {len(cases)*N_SEEDS} runs")
    results = []
    for case_id in cases:
        for s in range(N_SEEDS):
            try:
                r = await run_one(case_id, s)
                results.append(r)
                print(f"  [{case_id}/s{s}] PASS={r['is_correct']} cost=${r['cost']:.3f}")
            except Exception as e:
                print(f"  [{case_id}/s{s}] ERROR: {e}")
                results.append({"case_id": case_id, "seed_idx": s, "error": str(e), "condition": "v8_plus_neg"})
            (OUTPUT_ROOT / "main_results.json").write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    cost_total = sum(r.get("cost", 0) for r in results)
    print(f"\nMain eval total cost: ${cost_total:.2f}")
    print(f"Saved: {OUTPUT_ROOT / 'main_results.json'}")


if __name__ == "__main__":
    asyncio.run(main_async())
