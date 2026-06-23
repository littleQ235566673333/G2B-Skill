"""C-topo v3 ablation runner: 5 cases × 5 conditions × 1 seed = 25 runs.

Conditions: Pa (=Sa baseline), Pb, Pc, Sb, Sc.
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
CASES = ["oqa-112", "oqa-118", "oqa-130", "oqa-14", "oqa-35"]
CONDITIONS = ["Pa", "Pb", "Pc", "Sb", "Sc"]
SKILL_ROOT = Path("analysis/c_topo_ablation/v3_skills")
OUTPUT_ROOT = Path("analysis/c_topo_ablation/v3_results")


async def run_one(condition: str, case_id: str) -> dict:
    project_root = Path(".").resolve()
    out_dir = OUTPUT_ROOT / condition / case_id
    if out_dir.exists(): shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    skills_dir = out_dir / "_skills"; skills_dir.mkdir()
    shutil.copytree(SKILL_ROOT / condition / "officeqa", skills_dir / "officeqa")

    bench = get_bench("officeqa", data_dir="data/benchmarks/officeqa")
    dataset = bench.load_dataset()
    dataset_idx = next(i for i,e in enumerate(dataset) if e["id"]==case_id)
    seed_data = bench.prepare_seed_data(dataset, dataset_idx, out_dir)

    cost = CostTracker(MODEL)
    sem = asyncio.Semaphore(2)
    client = get_client_for_model(MODEL)

    print(f"  [{condition}/{case_id}] starting...")
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
        "condition": condition, "case_id": case_id,
        "is_correct": assessment["is_correct"],
        "cost": cost.total_cost, "elapsed": assessment["elapsed"],
    }


async def main_async():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    results = []
    # Run by condition (each condition's 5 cases sequentially before moving on)
    for condition in CONDITIONS:
        for case_id in CASES:
            try:
                r = await run_one(condition, case_id)
                results.append(r)
                print(f"  [{condition}/{case_id}] PASS={r['is_correct']} cost=${r['cost']:.3f}")
            except Exception as e:
                print(f"  [{condition}/{case_id}] ERROR: {e}")
                results.append({"condition": condition, "case_id": case_id, "error": str(e)})
            (OUTPUT_ROOT / "results.json").write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    # Tally
    print("\n=== v3 outcome by condition ===")
    print(f"{'cond':<6} {'pass / 5':<10} {'cost':<10}")
    for cond in CONDITIONS:
        n = sum(1 for r in results if r.get("condition")==cond and r.get("is_correct"))
        c = sum(r.get("cost", 0) for r in results if r.get("condition")==cond)
        print(f"  {cond:<6} {n}/5         ${c:.2f}")

    total = sum(r.get("cost", 0) for r in results)
    print(f"\nTotal cost: ${total:.2f}")


if __name__ == "__main__":
    asyncio.run(main_async())
