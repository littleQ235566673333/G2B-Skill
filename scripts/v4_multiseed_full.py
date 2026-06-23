"""v4 multi-seed full eval: 100 tasks × 3 seeds.

Paper-critical: gives v4 base multi-seed mean for the first time. Memory
[G2B overnight 2026-06-18 RESULTS] said "63%" but that was v5 multi-seed,
not v4. v4 single-seed 71% claim has never been multi-seed-verified.
"""
import asyncio, json, os, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"

from bench import get_bench
from pipeline.execution import run_execute
from runners.cost_tracker import CostTracker
from runners.model_dispatch import get_client_for_model
from runners.soffice import install_soffice_wrapper

N_SEEDS = 3
SKILL_ROOT = Path("results/runs/g2b-skill-spreadsheet_gpt-5.4_v4/train/final_skill")


async def main_async():
    workdir = Path("results/runs/g2b-skill-spreadsheet_gpt-5.4_v4/multiseed_full_eval")
    if workdir.exists(): shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    install_soffice_wrapper(workdir, Path("/tmp/skillgrad_soffice.lock"))

    bench = get_bench("spreadsheet", data_dir="results/normalized")
    dataset = bench.load_dataset()

    cost = CostTracker("gpt-5.4")
    sem = asyncio.Semaphore(8)
    client = get_client_for_model("gpt-5.4")

    async def one(idx, seed_idx):
        tid = str(dataset[idx]["id"])
        sd = bench.prepare_seed_data(
            dataset, idx, workdir,
            task_dir_name=f"task_{tid}_s{seed_idx}",
        )
        try:
            er = await run_execute(
                sd, sem, SKILL_ROOT, "gpt-5.4",
                project_root=Path(".").resolve(),
                max_turns=25, round_num=0, cost_tracker=cost,
                openai_client=client, skill_name="xlsx",
            )
            assess = await asyncio.to_thread(bench.assess, sd, er, 0)
            return {
                "id": tid, "seed": seed_idx,
                "cell": assess["accuracy"]["accuracy"],
                "hard": "PASS" if assess["is_correct"] else "FAIL",
            }
        except Exception as e:
            return {"id": tid, "seed": seed_idx,
                    "cell": 0.0, "hard": f"ERR {type(e).__name__}"}

    print(f"\n=== v4 multi-seed full eval: {len(dataset)} tasks × {N_SEEDS} seeds ===\n")
    coros = [one(i, s) for i in range(len(dataset)) for s in range(N_SEEDS)]
    results = await asyncio.gather(*coros)

    # Aggregate per (task)
    per_task = {}
    for r in results:
        per_task.setdefault(r["id"], []).append(r)

    # Per-seed summary
    print(f"\n=== per-seed summary ===\n")
    for s in range(N_SEEDS):
        seed_results = [r for r in results if r["seed"] == s]
        cell_mean = sum(r["cell"] for r in seed_results) / len(seed_results)
        hard_pass = sum(1 for r in seed_results if r["hard"] == "PASS") / len(seed_results)
        print(f"  seed {s}: {len(seed_results)} tasks, cell mean {cell_mean:.1%}, hard PASS {hard_pass:.1%}")

    # Multi-seed mean
    print(f"\n=== multi-seed aggregate ===\n")
    all_cells = [r["cell"] for r in results]
    all_hards = [r["hard"] == "PASS" for r in results]
    print(f"  cell mean (3-seed avg per task, then mean):")
    per_task_means = []
    for tid, runs in per_task.items():
        per_task_means.append(sum(r["cell"] for r in runs) / len(runs))
    print(f"    avg-of-task-means: {sum(per_task_means)/len(per_task_means):.1%}")
    print(f"    flat mean over all 300 trials: {sum(all_cells)/len(all_cells):.1%}")
    print(f"  hard PASS rate (flat over 300 trials): {sum(all_hards)/len(all_hards):.1%}")

    # Hard-PASS per seed (closer to "single-seed full eval" semantics)
    print(f"\n=== hard PASS counts per seed (out of 100) ===")
    for s in range(N_SEEDS):
        n_pass = sum(1 for r in results if r["seed"] == s and r["hard"] == "PASS")
        print(f"    seed {s}: {n_pass}/100")
    seed_pass_counts = [sum(1 for r in results if r["seed"] == s and r["hard"] == "PASS") for s in range(N_SEEDS)]
    print(f"    mean: {sum(seed_pass_counts)/len(seed_pass_counts):.1f}")
    import statistics
    print(f"    std:  {statistics.stdev(seed_pass_counts):.1f}")

    print(f"\nCost: ${cost.total_cost:.2f}")
    out = workdir / "summary.json"
    out.write_text(json.dumps({
        "results": results,
        "per_task": per_task,
        "seed_pass_counts": seed_pass_counts,
        "cost": cost.total_cost,
    }, indent=2))
    print(f"Wrote: {out}")


if __name__ == "__main__":
    asyncio.run(main_async())
