"""SkillGrad multi-seed eval on the same 100-task slice as v4 multi-seed.

Goal: apples-to-apples comparison between SkillGrad final SKILL.md and v4
final SKILL.md, both at 3-seed mean on the 100-task slice. Critical for
paper baseline numbers.

The 100-task slice is taken from v4's prior single-seed eval_summary.json
(those are exactly the 100 tasks SkillGrad's published 71% was scored on).
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
SKILL_ROOT = Path("/Users/unique/auto_research/Project/SkillGrad/results/runs/skillgrad_gpt-5.4/skills")


async def main_async():
    workdir = Path("results/runs/skillgrad-spreadsheet_gpt-5.4/multiseed_100slice_eval")
    if workdir.exists(): shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    install_soffice_wrapper(workdir, Path("/tmp/skillgrad_soffice.lock"))

    # Load 100-task slice from v4 prior eval
    v4_eval = json.load(open("results/runs/g2b-skill-spreadsheet_gpt-5.4_v4/eval/eval_summary.json"))
    slice_ids = [str(r["id"]) for r in v4_eval["results"]]
    print(f"100-task slice loaded: {len(slice_ids)} task ids")

    bench = get_bench("spreadsheet", data_dir="results/normalized")
    dataset = bench.load_dataset()
    id2idx = {str(s["id"]): i for i, s in enumerate(dataset)}
    indices = [id2idx[tid] for tid in slice_ids if tid in id2idx]
    print(f"Slice resolved to {len(indices)} indices in dataset of {len(dataset)}")

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

    print(f"\n=== SkillGrad multi-seed eval: 100-task slice × {N_SEEDS} seeds ({len(indices)*N_SEEDS} execs) ===\n")
    coros = [one(i, s) for i in indices for s in range(N_SEEDS)]
    results = await asyncio.gather(*coros)

    # Per-seed summary
    print(f"\n=== per-seed summary (100-task slice) ===\n")
    for s in range(N_SEEDS):
        sr = [r for r in results if r["seed"] == s]
        cell = sum(r["cell"] for r in sr) / len(sr)
        hard = sum(1 for r in sr if r["hard"] == "PASS")
        print(f"  seed {s}: {len(sr)} tasks, cell mean {cell:.1%}, hard PASS {hard}/{len(sr)}")

    # Multi-seed aggregate on 100-task slice
    all_cells = [r["cell"] for r in results]
    all_hards = [r["hard"] == "PASS" for r in results]
    hard_per_seed = [sum(1 for r in results if r["seed"] == s and r["hard"] == "PASS") for s in range(N_SEEDS)]
    import statistics
    print(f"\n=== aggregate on 100-task slice ===")
    print(f"  cell mean: {sum(all_cells)/len(all_cells):.1%}")
    print(f"  hard PASS rate: {sum(all_hards)/len(all_hards):.1%}")
    print(f"  hard PASS count per seed: {hard_per_seed}, mean {sum(hard_per_seed)/len(hard_per_seed):.1f}, std {statistics.stdev(hard_per_seed):.1f}")

    # Compare to v4 multi-seed reference
    print(f"\n=== comparison ===")
    print(f"  SkillGrad single-seed (published): 71/100")
    print(f"  v4 single-seed:                     71/100")
    print(f"  v4 multi-seed mean (this run):      61/100 (60, 61, 62)")
    print(f"  SkillGrad multi-seed mean (now):    {sum(hard_per_seed)/len(hard_per_seed):.0f}/100 ({', '.join(str(x) for x in hard_per_seed)})")
    delta = sum(hard_per_seed)/len(hard_per_seed) - 61
    if delta >= 5:
        verdict = f"SkillGrad +{delta:.0f}pp over v4 — real gap exists"
    elif delta <= -5:
        verdict = f"v4 +{-delta:.0f}pp over SkillGrad — G2B-Skill multi-seed wins!"
    else:
        verdict = f"parity (Δ {delta:+.0f}pp), within noise band"
    print(f"  → {verdict}")

    print(f"\nCost: ${cost.total_cost:.2f}")
    out = workdir / "summary.json"
    out.write_text(json.dumps({
        "results": results,
        "seed_pass_counts": hard_per_seed,
        "mean_pass": sum(hard_per_seed)/len(hard_per_seed),
        "verdict": verdict,
        "cost": cost.total_cost,
    }, indent=2))
    print(f"Wrote: {out}")


if __name__ == "__main__":
    asyncio.run(main_async())
