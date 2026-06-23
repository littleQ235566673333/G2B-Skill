"""Pre-check A eval: original SKILL.md vs mode-selector SKILL.md.

Single seed, both benches. GPT-5.4 backbone. Per brief.
"""
import argparse, asyncio, json, os, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"

from bench import get_bench
from pipeline.execution import run_execute
from runners.cost_tracker import CostTracker
from runners.model_dispatch import get_client_for_model
from runners.soffice import install_soffice_wrapper


BENCH_CONFIG = {
    "spreadsheet": {
        "skill_name": "xlsx",
        "data_dir": "results/normalized",
        "slice_source": "results/runs/g2b-skill-spreadsheet_gpt-5.4_v4/eval/eval_summary.json",
        "skill_original_root": Path("results/runs/g2b-v8_gpt-5.4/train/final_skill"),
        "skill_modeselector_root": Path("analysis/precheck_a/skills_modeselector"),
    },
    "wtq": {
        "skill_name": "wtq",
        "data_dir": "data/benchmarks/wikitablequestions",
        "slice_source": "analysis/precheck_a/wtq_slice.json",
        "skill_original_root": Path("results/runs/g2b-v8_gpt-5.4_wtq/train/final_skill"),
        "skill_modeselector_root": Path("analysis/precheck_a/skills_modeselector"),
    },
}


def load_slice_ids(path: str) -> list[str]:
    data = json.load(open(path))
    if isinstance(data, list):
        return [str(x) for x in data]
    return [str(r["id"]) for r in data["results"]]


async def run_eval(bench_name: str, variant: str, slice_ids: list[str], cost: CostTracker) -> dict:
    cfg = BENCH_CONFIG[bench_name]
    skill_name = cfg["skill_name"]
    skill_root = cfg["skill_original_root"] if variant == "original" else cfg["skill_modeselector_root"]

    workdir = Path(f"analysis/precheck_a/eval_{bench_name}_{variant}")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    install_soffice_wrapper(workdir, Path("/tmp/skillgrad_soffice.lock"))

    bench = get_bench(bench_name, data_dir=cfg["data_dir"])
    dataset = bench.load_dataset()
    id2idx = {str(s["id"]): i for i, s in enumerate(dataset)}
    indices = [id2idx[tid] for tid in slice_ids if tid in id2idx]
    print(f"  [{bench_name}/{variant}] resolved {len(indices)}/{len(slice_ids)} indices, skill={skill_root}")

    sem = asyncio.Semaphore(8)
    client = get_client_for_model("gpt-5.4")

    async def one(idx):
        tid = str(dataset[idx]["id"])
        sd = bench.prepare_seed_data(dataset, idx, workdir, task_dir_name=f"task_{tid}")
        try:
            er = await run_execute(
                sd, sem, skill_root, "gpt-5.4",
                project_root=Path(".").resolve(),
                max_turns=25, round_num=0,
                cost_tracker=cost, openai_client=client,
                skill_name=skill_name,
            )
            assess = await asyncio.to_thread(bench.assess, sd, er, 0)
            return {"id": tid, "cell": assess["accuracy"]["accuracy"],
                    "hard": "PASS" if assess["is_correct"] else "FAIL"}
        except Exception as e:
            return {"id": tid, "cell": 0.0, "hard": f"ERR {type(e).__name__}: {str(e)[:80]}"}

    results = await asyncio.gather(*[one(i) for i in indices])
    cell_mean = sum(r["cell"] for r in results) / len(results) if results else 0
    hard_pass = sum(1 for r in results if r["hard"] == "PASS")

    out = {"bench": bench_name, "variant": variant, "n": len(results),
           "hard_pass": hard_pass, "cell_mean": cell_mean,
           "skill_root": str(skill_root), "results": results}
    out_path = Path(f"analysis/precheck_a/eval_{bench_name}_{variant}_summary.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"  [{bench_name}/{variant}] hard PASS = {hard_pass}/{len(results)}, cell mean = {cell_mean:.1%}")
    return out


async def main_async(bench_name: str):
    cfg = BENCH_CONFIG[bench_name]
    slice_ids = load_slice_ids(cfg["slice_source"])
    print(f"=== Pre-check A eval: {bench_name}, {len(slice_ids)} tasks ===")
    cost = CostTracker("gpt-5.4")

    print("\n--- ORIGINAL ---")
    orig = await run_eval(bench_name, "original", slice_ids, cost)
    print("\n--- MODE-SELECTOR ---")
    mode = await run_eval(bench_name, "modeselector", slice_ids, cost)

    diff = mode["hard_pass"] - orig["hard_pass"]
    print(f"\n=== {bench_name} comparison ===")
    print(f"  original:      {orig['hard_pass']}/{orig['n']}")
    print(f"  mode-selector: {mode['hard_pass']}/{mode['n']}")
    print(f"  diff:          {diff:+d} pp")
    print(f"  cost:          ${cost.total_cost:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", required=True, choices=["spreadsheet", "wtq"])
    args = parser.parse_args()
    asyncio.run(main_async(args.bench))
