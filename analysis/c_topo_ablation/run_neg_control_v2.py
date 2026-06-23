"""C-topo v2 negative control: v8+neg should not regress on stable_pass cases.

Per protocol: 3 cases × 3 seeds × v8+neg condition.
Use v1 cases that were stable_pass in pilot: oqa-25, oqa-33, oqa-40.

If aggregate regression > 1pp absolute or any single case drops ≥ 2/3 seeds,
flag in REPORT.
"""
from __future__ import annotations
import asyncio, json, os, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"

from bench import get_bench
from pipeline.execution import run_execute
from runners.cost_tracker import CostTracker
from runners.model_dispatch import get_client_for_model

MODEL = "gpt-5.4"
NEG_CONTROL = ["oqa-25", "oqa-33", "oqa-40"]
N_SEEDS = 3
SKILL_DIR = Path("analysis/c_topo_ablation/v2_skill_v8_plus_neg")
OUTPUT_ROOT = Path("analysis/c_topo_ablation/v2_neg_control")


async def run_one(case_id: str, seed_idx: int) -> dict:
    project_root = Path(".").resolve()
    out_dir = OUTPUT_ROOT / f"{case_id}_s{seed_idx}"
    if out_dir.exists(): shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    skills_dir = out_dir / "_skills"; skills_dir.mkdir()
    shutil.copytree(SKILL_DIR / "officeqa", skills_dir / "officeqa")

    bench = get_bench("officeqa", data_dir="data/benchmarks/officeqa")
    dataset = bench.load_dataset()
    dataset_idx = next(i for i,e in enumerate(dataset) if e["id"]==case_id)
    seed_data = bench.prepare_seed_data(dataset, dataset_idx, out_dir)

    cost = CostTracker(MODEL)
    sem = asyncio.Semaphore(2)
    client = get_client_for_model(MODEL)

    print(f"  [{case_id}/s{seed_idx}] starting...")
    exec_result = await run_execute(
        seed_data=seed_data, semaphore=sem, skills_dir=skills_dir,
        model=MODEL, project_root=project_root, max_turns=30, round_num=0,
        cost_tracker=cost, openai_client=client, skill_name="officeqa",
    )
    assessment = bench.assess(seed_data, exec_result, round_num=0)
    return {
        "case_id": case_id, "seed_idx": seed_idx,
        "is_correct": assessment["is_correct"], "cost": cost.total_cost,
    }


async def main_async():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    results = []
    for case_id in NEG_CONTROL:
        for s in range(N_SEEDS):
            try:
                r = await run_one(case_id, s)
                results.append(r)
                print(f"  [{case_id}/s{s}] PASS={r['is_correct']} cost=${r['cost']:.3f}")
            except Exception as e:
                print(f"  [{case_id}/s{s}] ERROR: {e}")
                results.append({"case_id": case_id, "seed_idx": s, "error": str(e)})
            (OUTPUT_ROOT / "results.json").write_text(
                json.dumps(results, indent=2), encoding="utf-8")
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main_async())
