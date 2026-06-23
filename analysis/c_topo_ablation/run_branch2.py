"""C-topo v2 Branch 2 expansion: add 3 SG-exact remaining cases.

Cases: oqa-58, oqa-91, oqa-112 (rel_err < 0.10 but SG nailed).
5 seeds each = 15 runs.

If after this, total stable_fail < 8, cascade to Branch 3.
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
B2_CASES = ["oqa-58", "oqa-91", "oqa-112"]
N_SEEDS = 5
SKILL_SRC = Path("results/runs/g2b-v8_gpt-5.4_oqa-gpt54-smoke/train/final_skill")
OUTPUT_ROOT = Path("analysis/c_topo_ablation/v2_branch2")


async def run_one(case_id: str, seed_idx: int) -> dict:
    project_root = Path(".").resolve()
    out_dir = OUTPUT_ROOT / f"{case_id}_s{seed_idx}"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    skills_dir = out_dir / "_skills"
    skills_dir.mkdir(parents=True)
    shutil.copytree(SKILL_SRC / "officeqa", skills_dir / "officeqa")

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
    }


async def main_async():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    results = []
    for case_id in B2_CASES:
        for s in range(N_SEEDS):
            try:
                r = await run_one(case_id, s)
                results.append(r)
                print(f"  [{case_id}/s{s}] PASS={r['is_correct']} cost=${r['cost']:.3f}")
            except Exception as e:
                print(f"  [{case_id}/s{s}] ERROR: {e}")
                results.append({"case_id": case_id, "seed_idx": s, "error": str(e)})
            (OUTPUT_ROOT / "branch2_results.json").write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== BRANCH 2 TALLY ===")
    classifications = {}
    for cid in B2_CASES:
        passes = sum(1 for r in results if r.get("case_id")==cid and r.get("is_correct"))
        cls = "stable_fail" if passes <= 1 else "stable_pass" if passes >= 4 else "mid"
        classifications[cid] = (passes, cls)
        print(f"  {cid}: {passes}/5 → {cls}")

    # Combine with pilot
    pilot = json.loads(Path("analysis/c_topo_ablation/v2_pilot/pilot_summary.json").read_text())
    total_sf = pilot["stable_fail_count"]
    for cid, (p, k) in classifications.items():
        if k == "stable_fail": total_sf += 1

    print(f"\nTotal stable_fail (pilot+B2): {total_sf}")
    if total_sf >= 8:
        next_step = f"Main eval on {total_sf} stable_fail cases"
    else:
        next_step = "CASCADE to Branch 3 (random 30 v8-fail)"
    print(f"Next: {next_step}")

    summary = {
        "branch": "Branch 2",
        "b2_cases": B2_CASES,
        "per_case": {c: {"passes": p, "classification": k} for c,(p,k) in classifications.items()},
        "total_stable_fail_after_b2": total_sf,
        "cost": sum(r.get("cost", 0) for r in results),
        "next_step": next_step,
    }
    (OUTPUT_ROOT / "branch2_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main_async())
