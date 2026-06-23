"""C-topo v2 stage P (pilot): v8 5-seed stability filter on 6 v1 candidates.

Per protocol_v2_multiseed.md:
  - Pilot pool: oqa-14, -16, -25, -33, -40, -129 (rel_err>0.10, SG exact, ≠oqa-51)
  - 5 seeds × 6 cases = 30 v8 runs
  - Output: per-case pass count + classification (stable_fail / mid / stable_pass)

Per-seed control: we vary the executor's randomization by setting
seed-derived temperature + restarting the agent runner with a new
session each time. The current pipeline doesn't expose a per-call
seed knob to the model API, so multi-seed here means N independent
re-runs on the same task — natural variation comes from
non-determinism of the LLM endpoint at temperature=1.0 (used for
group rollouts) or default temperature (this case).
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
PILOT_CASES = ["oqa-14", "oqa-16", "oqa-25", "oqa-33", "oqa-40", "oqa-129"]
N_SEEDS = 5
SKILL_SRC = Path("results/runs/g2b-v8_gpt-5.4_oqa-gpt54-smoke/train/final_skill")
OUTPUT_ROOT = Path("analysis/c_topo_ablation/v2_pilot")


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

    src_workdir = Path(seed_data["task_workdir"])
    for fname in ["output.txt", "execution_trace_r0.md", "assessment_r0.json"]:
        sp = src_workdir / fname
        dp = out_dir / fname
        if sp.exists():
            shutil.copy2(sp, dp)

    is_correct = assessment["is_correct"]
    print(f"  [{case_id}/seed{seed_idx}] PASS={is_correct} cost=${cost.total_cost:.3f}")
    return {
        "case_id": case_id,
        "seed_idx": seed_idx,
        "is_correct": is_correct,
        "cost": cost.total_cost,
        "elapsed": assessment["elapsed"],
    }


async def main_async():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    results = []
    for case_id in PILOT_CASES:
        for s in range(N_SEEDS):
            try:
                r = await run_one(case_id, s)
                results.append(r)
            except Exception as e:
                print(f"  [{case_id}/seed{s}] ERROR: {e}")
                results.append({"case_id": case_id, "seed_idx": s, "error": str(e)})
            # Periodic save
            (OUTPUT_ROOT / "pilot_results.json").write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    # Tally
    print("\n=== PILOT TALLY ===")
    print(f"{'case':<10} {'pass / 5':<10} {'classification'}")
    classifications = {}
    for case_id in PILOT_CASES:
        passes = sum(1 for r in results if r.get("case_id") == case_id and r.get("is_correct"))
        if passes <= 1:
            cls = "stable_fail"
        elif passes >= 4:
            cls = "stable_pass"
        else:
            cls = "mid"
        classifications[case_id] = (passes, cls)
        print(f"  {case_id:<10} {passes}/5         {cls}")

    n_sf = sum(1 for c, (p, k) in classifications.items() if k == "stable_fail")
    n_sp = sum(1 for c, (p, k) in classifications.items() if k == "stable_pass")
    n_mid = 6 - n_sf - n_sp
    total_cost = sum(r.get("cost", 0) for r in results)
    print(f"\nstable_fail: {n_sf}/6, stable_pass: {n_sp}/6, mid: {n_mid}/6")
    print(f"Total cost: ${total_cost:.2f}")

    # Branch decision
    if n_sf >= 5:
        branch = "Branch 1: small expand"
    elif n_sf >= 2:
        branch = "Branch 2: SG-exact extension (same action as Branch 1)"
    else:
        branch = "Branch 3: random 30 v8-fail"
    print(f"\nFrozen branch decision: {branch}")

    summary = {
        "pilot_cases": PILOT_CASES,
        "n_seeds": N_SEEDS,
        "per_case": {c: {"passes": p, "classification": k} for c, (p, k) in classifications.items()},
        "stable_fail_count": n_sf,
        "stable_pass_count": n_sp,
        "mid_count": n_mid,
        "total_cost": total_cost,
        "branch_decision": branch,
    }
    (OUTPUT_ROOT / "pilot_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSummary: {OUTPUT_ROOT / 'pilot_summary.json'}")


if __name__ == "__main__":
    asyncio.run(main_async())
