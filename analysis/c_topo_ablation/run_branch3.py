"""C-topo v2 Branch 3: random 30 v8-fail cases × 5 seeds.

Frozen pool: sorted v8-fail tids[:30] from analysis/c_topo_ablation/v2_branch3_pool.json.
Skips cases already evaluated in pilot or branch2 (reuses those results).

Triggered automatically when pilot+B2 stable_fail count < 8.
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
SKILL_SRC = Path("results/runs/g2b-v8_gpt-5.4_oqa-gpt54-smoke/train/final_skill")
OUTPUT_ROOT = Path("analysis/c_topo_ablation/v2_branch3")

# Reuse already-evaluated pilot / B2 cases to save budget
ALREADY_EVALUATED = {
    "oqa-14":  "v2_pilot",
    "oqa-16":  "v2_pilot",
    "oqa-25":  "v2_pilot",
    "oqa-33":  "v2_pilot",
    "oqa-40":  "v2_pilot",
    "oqa-129": "v2_pilot",
    "oqa-58":  "v2_branch2",
    "oqa-91":  "v2_branch2",
    "oqa-112": "v2_branch2",
}


def _load_existing(case_id: str, source_root: str) -> list[dict]:
    """Load N_SEEDS existing eval records for a case from pilot/B2 dirs."""
    src_root = Path(f"analysis/c_topo_ablation/{source_root}")
    if source_root == "v2_pilot":
        results_file = src_root / "pilot_results.json"
    else:
        results_file = src_root / "branch2_results.json"
    if not results_file.exists():
        return []
    all_r = json.loads(results_file.read_text())
    return [r for r in all_r if r.get("case_id") == case_id]


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
    pool = json.loads(Path("analysis/c_topo_ablation/v2_branch3_pool.json").read_text())
    cases_30 = pool["frozen_30"]

    results: list[dict] = []
    for case_id in cases_30:
        # Reuse if already evaluated
        if case_id in ALREADY_EVALUATED:
            existing = _load_existing(case_id, ALREADY_EVALUATED[case_id])
            for r in existing:
                results.append({**r, "source": ALREADY_EVALUATED[case_id]})
            print(f"  [{case_id}] reused {len(existing)} from {ALREADY_EVALUATED[case_id]}")
            continue
        for s in range(N_SEEDS):
            try:
                r = await run_one(case_id, s)
                results.append({**r, "source": "v2_branch3"})
                print(f"  [{case_id}/s{s}] PASS={r['is_correct']} cost=${r['cost']:.3f}")
            except Exception as e:
                print(f"  [{case_id}/s{s}] ERROR: {e}")
                results.append({"case_id": case_id, "seed_idx": s, "error": str(e), "source": "v2_branch3"})
            (OUTPUT_ROOT / "branch3_results.json").write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    # Tally
    print("\n=== BRANCH 3 + PRIOR FILTER TALLY ===")
    classifications = {}
    for cid in cases_30:
        passes = sum(1 for r in results if r.get("case_id")==cid and r.get("is_correct"))
        cls = "stable_fail" if passes <= 1 else "stable_pass" if passes >= 4 else "mid"
        classifications[cid] = (passes, cls)

    n_sf = sum(1 for c,(p,k) in classifications.items() if k == "stable_fail")
    n_sp = sum(1 for c,(p,k) in classifications.items() if k == "stable_pass")
    n_mid = 30 - n_sf - n_sp
    print(f"stable_fail: {n_sf}/30, stable_pass: {n_sp}/30, mid: {n_mid}/30")

    print("\nstable_fail cases:")
    sf_cases = [c for c,(p,k) in classifications.items() if k=="stable_fail"]
    for c in sf_cases: print(f"  {c}: {classifications[c][0]}/5")

    new_cost = sum(r.get("cost", 0) for r in results if r.get("source") == "v2_branch3")
    print(f"\nNew Branch 3 cost: ${new_cost:.2f}")

    summary = {
        "branch": "Branch 3 (with pilot+B2 reuse)",
        "frozen_30_cases": cases_30,
        "per_case": {c: {"passes": p, "classification": k} for c,(p,k) in classifications.items()},
        "stable_fail_cases": sf_cases,
        "stable_fail_count": n_sf,
        "stable_pass_count": n_sp,
        "mid_count": n_mid,
        "new_cost": new_cost,
        "halt_threshold_8_met": n_sf >= 8,
    }
    (OUTPUT_ROOT / "branch3_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSummary: {OUTPUT_ROOT / 'branch3_summary.json'}")
    if n_sf >= 8:
        print(f"\n→ Proceed to main eval on {min(n_sf, 10)} stable_fail cases")
    else:
        print(f"\n→ HALT (per protocol): {n_sf} < 8 stable_fail")


if __name__ == "__main__":
    asyncio.run(main_async())
