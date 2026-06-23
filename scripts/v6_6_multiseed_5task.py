"""5-task × 3-seed × 3-version multi-seed mechanism comparison.

Replaces the failed single-seed step 0. Goal: get hard data on whether
v6.6's gate killed 9391 (or that's noise) and whether v6.5 mechanism gain
on 56378 is reproducible at multi-seed.
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

TASKS = ["56378", "51262", "9391", "535-20", "168-17"]
N_SEEDS = 3

VERSIONS = {
    "v4":   Path("results/runs/g2b-skill-spreadsheet_gpt-5.4_v4/train/final_skill"),
    "v6.5": Path("results/runs/g2b-skill-spreadsheet_gpt-5.4_v6_5_patchertest/skills"),
    "v6.6": Path("results/skill_v6_6"),
}


async def main_async():
    workdir = Path("results/runs/g2b-skill-spreadsheet_gpt-5.4_v6_6/multiseed_5task")
    if workdir.exists(): shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    install_soffice_wrapper(workdir, Path("/tmp/skillgrad_soffice.lock"))

    bench = get_bench("spreadsheet", data_dir="results/normalized")
    dataset = bench.load_dataset()
    id2idx = {str(s["id"]): i for i, s in enumerate(dataset)}

    cost = CostTracker("gpt-5.4")
    sem = asyncio.Semaphore(6)
    client = get_client_for_model("gpt-5.4")

    async def one(version, skill_root, tid, seed_idx):
        idx = id2idx[tid]
        sd = bench.prepare_seed_data(
            dataset, idx, workdir,
            task_dir_name=f"{version}_{tid}_s{seed_idx}",
        )
        try:
            er = await run_execute(
                sd, sem, skill_root, "gpt-5.4",
                project_root=Path(".").resolve(),
                max_turns=25, round_num=0, cost_tracker=cost,
                openai_client=client, skill_name="xlsx",
            )
            assess = await asyncio.to_thread(bench.assess, sd, er, 0)
            return {
                "version": version, "id": tid, "seed": seed_idx,
                "cell": assess["accuracy"]["accuracy"],
                "hard": "PASS" if assess["is_correct"] else "FAIL",
            }
        except Exception as e:
            return {"version": version, "id": tid, "seed": seed_idx,
                    "cell": 0.0, "hard": f"ERR {type(e).__name__}"}

    print(f"\n=== multi-seed 5-task × 3-seed × 3-version ({len(VERSIONS)*len(TASKS)*N_SEEDS} execs) ===\n")
    coros = []
    for vname, sroot in VERSIONS.items():
        for tid in TASKS:
            for s in range(N_SEEDS):
                coros.append(one(vname, sroot, tid, s))
    results = await asyncio.gather(*coros)

    # Aggregate
    agg = {}
    for r in results:
        agg.setdefault((r["version"], r["id"]), []).append(r)

    print(f"\n{'task':>10s} | {'version':>6s} | {'cell s0,s1,s2':>15s} | {'mean':>6s} | hard PASS count")
    print("-" * 75)
    for tid in TASKS:
        for vname in VERSIONS:
            runs = sorted(agg[(vname, tid)], key=lambda r: r["seed"])
            cells = [r["cell"] for r in runs]
            cells_str = ",".join(f"{c:.0%}" for c in cells)
            mean = sum(cells) / len(cells)
            n_pass = sum(1 for r in runs if r["hard"] == "PASS")
            print(f"{tid:>10s} | {vname:>6s} | {cells_str:>15s} | {mean:>5.0%} | {n_pass}/{N_SEEDS}")
        print()

    # Per-version overall
    print(f"\n=== per-version aggregate ===\n")
    print(f"{'version':>6s} | {'mean cell':>9s} | {'hard PASS rate':>15s}")
    for vname in VERSIONS:
        all_cells = []
        all_hards = []
        for tid in TASKS:
            runs = agg[(vname, tid)]
            all_cells.extend(r["cell"] for r in runs)
            all_hards.extend(r["hard"] == "PASS" for r in runs)
        mean_cell = sum(all_cells) / len(all_cells)
        pass_rate = sum(all_hards) / len(all_hards)
        print(f"{vname:>6s} | {mean_cell:>9.1%} | {pass_rate:>15.1%}")

    print(f"\nCost: ${cost.total_cost:.3f}")
    out = workdir.parent / "multiseed_5task_summary.json"
    out.write_text(json.dumps({
        "results": results,
        "agg": {f"{k[0]}__{k[1]}": v for k, v in agg.items()},
        "cost": cost.total_cost,
    }, indent=2))
    print(f"Wrote: {out}")


if __name__ == "__main__":
    asyncio.run(main_async())
