"""v8 multi-seed eval — 2 additional seeds on 100-task slice (seed 0 already
done at hard=68/100, cell=81.0%). Combined with seed 0, gives 3-seed mean.
"""
import asyncio, json, os, shutil, sys, statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"

from bench import get_bench
from pipeline.execution import run_execute
from runners.cost_tracker import CostTracker
from runners.model_dispatch import get_client_for_model
from runners.soffice import install_soffice_wrapper

SKILL_ROOT = Path("results/runs/g2b-v8_gpt-5.4/train/final_skill")
N_ADDITIONAL_SEEDS = 2  # seeds 1 and 2; seed 0 already done in singleseed eval


async def main_async():
    workdir = Path("results/runs/g2b-v8_gpt-5.4/eval_100slice_multiseed")
    if workdir.exists(): shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    install_soffice_wrapper(workdir, Path("/tmp/skillgrad_soffice.lock"))

    v4_eval = json.load(open("results/runs/g2b-skill-spreadsheet_gpt-5.4_v4/eval/eval_summary.json"))
    slice_ids = [str(r["id"]) for r in v4_eval["results"]]
    bench = get_bench("spreadsheet", data_dir="results/normalized")
    dataset = bench.load_dataset()
    id2idx = {str(s["id"]): i for i, s in enumerate(dataset)}
    indices = [id2idx[tid] for tid in slice_ids if tid in id2idx]

    cost = CostTracker("gpt-5.4")
    sem = asyncio.Semaphore(8)
    client = get_client_for_model("gpt-5.4")

    async def one(idx, seed_idx):
        tid = str(dataset[idx]["id"])
        sd = bench.prepare_seed_data(dataset, idx, workdir, task_dir_name=f"task_{tid}_s{seed_idx}")
        try:
            er = await run_execute(sd, sem, SKILL_ROOT, "gpt-5.4",
                project_root=Path(".").resolve(), max_turns=25, round_num=0,
                cost_tracker=cost, openai_client=client, skill_name="xlsx")
            assess = await asyncio.to_thread(bench.assess, sd, er, 0)
            return {"id": tid, "seed": seed_idx, "cell": assess["accuracy"]["accuracy"],
                    "hard": "PASS" if assess["is_correct"] else "FAIL"}
        except Exception as e:
            return {"id": tid, "seed": seed_idx, "cell": 0.0, "hard": f"ERR {type(e).__name__}"}

    print(f"\n=== v8 multi-seed eval: {N_ADDITIONAL_SEEDS} additional seeds × 100 tasks ===\n")
    coros = [one(i, s) for i in indices for s in range(1, N_ADDITIONAL_SEEDS + 1)]
    new_results = await asyncio.gather(*coros)

    # Load seed 0 from prior eval
    seed0 = json.load(open("results/runs/g2b-v8_gpt-5.4/eval_100slice_singleseed_summary.json"))["results"]
    seed0_results = [{**r, "seed": 0} for r in seed0]
    all_results = seed0_results + new_results

    # Per-seed pass count
    print(f"\n=== per-seed PASS counts (out of 100) ===")
    pass_counts = []
    for s in range(0, N_ADDITIONAL_SEEDS + 1):
        sr = [r for r in all_results if r["seed"] == s]
        n = sum(1 for r in sr if r["hard"] == "PASS")
        cell = sum(r["cell"] for r in sr) / len(sr) if sr else 0
        pass_counts.append(n)
        print(f"  seed {s}: {n}/100 hard PASS, cell mean {cell:.1%}")

    mean_pass = sum(pass_counts) / len(pass_counts)
    std_pass = statistics.stdev(pass_counts) if len(pass_counts) > 1 else 0
    print(f"\n=== aggregate ===")
    print(f"  v8 multi-seed PASS counts: {pass_counts}")
    print(f"  v8 multi-seed mean: {mean_pass:.1f} ± {std_pass:.1f}")
    print(f"\n=== comparison ===")
    print(f"  v4 multi-seed mean:        61 ± 1.0")
    print(f"  SkillGrad multi-seed mean: 69 ± 2.1")
    print(f"  v7 single (1 seed):        64")
    print(f"  v8 multi-seed mean:        {mean_pass:.1f} ± {std_pass:.1f}  [3 seeds]")
    delta_skillgrad = mean_pass - 69
    if mean_pass >= 69:
        verdict = f"≥ SkillGrad multi-seed mean (Δ {delta_skillgrad:+.1f}pp). PARITY OR BEYOND."
    elif mean_pass >= 67:
        verdict = f"within noise band of SkillGrad ({delta_skillgrad:+.1f}pp, std overlap). PARITY."
    elif mean_pass >= 64:
        verdict = f"above v7 64 but below SkillGrad ({delta_skillgrad:+.1f}pp). MODEST IMPROVEMENT."
    else:
        verdict = f"single-seed 68 was upper-tail luck; multi-seed below v7."
    print(f"  → {verdict}")

    print(f"\nCost (additional seeds): ${cost.total_cost:.2f}")

    out = workdir.parent / "eval_100slice_multiseed_summary.json"
    out.write_text(json.dumps({
        "all_results": all_results, "pass_counts": pass_counts,
        "mean_pass": mean_pass, "std_pass": std_pass,
        "verdict": verdict, "additional_cost": cost.total_cost,
    }, indent=2))
    print(f"Wrote: {out}")


if __name__ == "__main__":
    asyncio.run(main_async())
