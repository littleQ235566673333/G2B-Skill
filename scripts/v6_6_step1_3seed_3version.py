"""Step 1: 10 formula variance tasks × 3 seeds × {v4, v6.5, v6.6} = 90 execs.

Decision matrix in analysis/step1_pre_commit_matrix.md (committed before run).
Unlike single-seed step 0 which deceived us with 9391 100→0 swing, this gives
3-seed mean per (version, task) for true mechanism comparison.
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

TASKS = ['7665', '55979', '36097', '38537', '9448', '59224', '46897', '524-31', '37900', '52541']
N_SEEDS = 3

VERSIONS = {
    "v4":   Path("results/runs/g2b-skill-spreadsheet_gpt-5.4_v4/train/final_skill"),
    "v6.5": Path("results/runs/g2b-skill-spreadsheet_gpt-5.4_v6_5_patchertest/skills"),
    "v6.6": Path("results/skill_v6_6"),
}


async def main_async():
    workdir = Path("results/runs/g2b-skill-spreadsheet_gpt-5.4_v6_6/step1_formula10_3seed_3version")
    if workdir.exists(): shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    install_soffice_wrapper(workdir, Path("/tmp/skillgrad_soffice.lock"))

    bench = get_bench("spreadsheet", data_dir="results/normalized")
    dataset = bench.load_dataset()
    id2idx = {str(s["id"]): i for i, s in enumerate(dataset)}

    cost = CostTracker("gpt-5.4")
    sem = asyncio.Semaphore(8)
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

    print(f"\n=== step 1: 10 formula × 3 seed × 3 version ({len(VERSIONS)*len(TASKS)*N_SEEDS} execs) ===\n")
    coros = []
    for vname, sroot in VERSIONS.items():
        for tid in TASKS:
            for s in range(N_SEEDS):
                coros.append(one(vname, sroot, tid, s))
    results = await asyncio.gather(*coros)

    agg = {}
    for r in results:
        agg.setdefault((r["version"], r["id"]), []).append(r)

    print(f"\n{'task':>10s} | {'version':>6s} | {'cell s0,s1,s2':>15s} | {'mean':>6s} | hard")
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

    # Per-version aggregate (decision input)
    print(f"\n=== per-version aggregate over 10 tasks ===\n")
    per_v = {}
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
        per_v[vname] = {"mean_cell": mean_cell, "pass_rate": pass_rate}
        print(f"{vname:>6s} | {mean_cell:>9.1%} | {pass_rate:>15.1%}")

    print(f"\n=== decision per pre-commit matrix ===\n")
    d_v4 = per_v["v6.6"]["mean_cell"] - per_v["v4"]["mean_cell"]
    d_v65 = per_v["v6.6"]["mean_cell"] - per_v["v6.5"]["mean_cell"]
    print(f"  v6.6 - v4:    {d_v4*100:+.1f}pp")
    print(f"  v6.6 - v6.5:  {d_v65*100:+.1f}pp")
    if d_v4 >= 0.10 and d_v65 >= 0.05:
        case = "A — v6.6 真好 → step 2 stable region with v6.6"
    elif d_v4 >= 0.05 and abs(d_v65) <= 0.03:
        case = "B — v6.6 ≈ v6.5 → step 2 stable region with v6.5 (simpler)"
    elif per_v["v6.6"]["mean_cell"] < per_v["v6.5"]["mean_cell"] - 0.03 or \
         per_v["v6.6"]["mean_cell"] < per_v["v4"]["mean_cell"]:
        case = "C — v6.6 under-performs → STOP, pivot decision"
    else:
        case = "EDGE — between cases, manual review"
    print(f"  → {case}")

    print(f"\nCost: ${cost.total_cost:.3f}")
    out = workdir.parent / "step1_summary.json"
    out.write_text(json.dumps({
        "results": results,
        "agg": {f"{k[0]}__{k[1]}": v for k, v in agg.items()},
        "per_version": per_v,
        "decision": case,
        "cost": cost.total_cost,
    }, indent=2))
    print(f"Wrote: {out}")


if __name__ == "__main__":
    asyncio.run(main_async())
