"""v8 single-seed eval on 100-task slice. Comparison target: SkillGrad single
71/100, v4 single 71/100. Decision: if v7 ≥ 70 → multi-seed for paper number.
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

SKILL_ROOT = Path("results/runs/g2b-v8_gpt-5.4/train/final_skill")


async def main_async():
    workdir = Path("results/runs/g2b-v8_gpt-5.4/eval_100slice_singleseed")
    if workdir.exists(): shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    install_soffice_wrapper(workdir, Path("/tmp/skillgrad_soffice.lock"))

    v4_eval = json.load(open("results/runs/g2b-skill-spreadsheet_gpt-5.4_v4/eval/eval_summary.json"))
    slice_ids = [str(r["id"]) for r in v4_eval["results"]]
    print(f"100-task slice: {len(slice_ids)} ids")

    bench = get_bench("spreadsheet", data_dir="results/normalized")
    dataset = bench.load_dataset()
    id2idx = {str(s["id"]): i for i, s in enumerate(dataset)}
    indices = [id2idx[tid] for tid in slice_ids if tid in id2idx]
    print(f"resolved {len(indices)} indices")

    cost = CostTracker("gpt-5.4")
    sem = asyncio.Semaphore(8)
    client = get_client_for_model("gpt-5.4")

    async def one(idx):
        tid = str(dataset[idx]["id"])
        sd = bench.prepare_seed_data(dataset, idx, workdir, task_dir_name=f"task_{tid}")
        try:
            er = await run_execute(sd, sem, SKILL_ROOT, "gpt-5.4",
                project_root=Path(".").resolve(), max_turns=25, round_num=0,
                cost_tracker=cost, openai_client=client, skill_name="xlsx")
            assess = await asyncio.to_thread(bench.assess, sd, er, 0)
            return {"id": tid, "cell": assess["accuracy"]["accuracy"],
                    "hard": "PASS" if assess["is_correct"] else "FAIL"}
        except Exception as e:
            return {"id": tid, "cell": 0.0, "hard": f"ERR {type(e).__name__}"}

    print(f"\n=== v8 single-seed eval on 100-task slice ({len(indices)} execs) ===\n")
    results = await asyncio.gather(*[one(i) for i in indices])

    cell_mean = sum(r["cell"] for r in results) / len(results)
    hard_pass = sum(1 for r in results if r["hard"] == "PASS")
    print(f"\n=== v8 single-seed result ===")
    print(f"  hard PASS:  {hard_pass}/100")
    print(f"  cell mean:  {cell_mean:.1%}")
    print(f"  cost:       ${cost.total_cost:.2f}")
    print(f"\n=== comparison ===")
    print(f"  SkillGrad single (published): 71/100")
    print(f"  SkillGrad multi-seed mean:    69/100")
    print(f"  v4 single (published):        71/100")
    print(f"  v4 multi-seed mean:           61/100")
    print(f"  **v7 single (this run):       {hard_pass}/100**")
    if hard_pass >= 70:
        verdict = "≥ SkillGrad single 71 — STRONG, run multi-seed for paper"
    elif hard_pass >= 65:
        verdict = "in noise band of SkillGrad single 71 — run multi-seed to confirm"
    elif hard_pass >= 61:
        verdict = "above v4 multi-seed but below SkillGrad single — group signal helps but doesn't beat"
    else:
        verdict = "below v4 multi-seed — group signal hurts or noise"
    print(f"  → {verdict}")

    Path("results/runs/g2b-v8_gpt-5.4/eval_100slice_singleseed_summary.json").write_text(
        json.dumps({"results": results, "hard_pass": hard_pass, "cell_mean": cell_mean,
                    "cost": cost.total_cost, "verdict": verdict}, indent=2))


if __name__ == "__main__":
    asyncio.run(main_async())
