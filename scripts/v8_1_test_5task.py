"""v8.1 5-task test: 3 motivation SG-win tasks + 2 hold-out SG-win tasks.

Pass criteria: ≥2 motivation unlock AND ≥1 hold-out unlock.
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

SKILL_ROOT = Path("results/skill_v8_1")
MOTIVATION = ["9391", "51262", "55468"]  # known SG-win, used for rule selection motivation
HOLDOUT    = ["55979", "5835"]            # other SG-win, NOT used in motivation

# v8 multi-seed result on these tasks (for "previously failing" baseline check)
# Loaded dynamically below


async def main_async():
    workdir = Path("results/runs/g2b-v8_1_gpt-5.4_5task_test")
    if workdir.exists(): shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    install_soffice_wrapper(workdir, Path("/tmp/skillgrad_soffice.lock"))

    bench = get_bench("spreadsheet", data_dir="results/normalized")
    dataset = bench.load_dataset()
    id2idx = {str(s["id"]): i for i, s in enumerate(dataset)}

    # Get v8 multi-seed baseline for these tasks
    v8_multi = json.load(open("results/runs/g2b-v8_gpt-5.4/eval_100slice_multiseed_summary.json"))
    v8_per_task = {}
    for r in v8_multi["all_results"]:
        v8_per_task.setdefault(r["id"], []).append(r["hard"] == "PASS")

    print(f"\n=== v8 multi-seed baseline (3 seeds) on test tasks ===")
    for tid in MOTIVATION + HOLDOUT:
        runs = v8_per_task.get(tid, [])
        n_pass = sum(runs)
        kind = "MOTIVATION" if tid in MOTIVATION else "HOLDOUT"
        print(f"  {tid} ({kind}): v8 multi-seed {n_pass}/3 PASS")

    cost = CostTracker("gpt-5.4")
    sem = asyncio.Semaphore(5)
    client = get_client_for_model("gpt-5.4")

    async def one(tid):
        idx = id2idx[tid]
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

    print(f"\n=== v8.1 single-seed eval on 5 SG-win tasks ===\n")
    tasks = MOTIVATION + HOLDOUT
    results = await asyncio.gather(*[one(t) for t in tasks])

    print(f"{'task':>8} | {'kind':>10} | {'v8 multi-seed':>13} | {'v8.1 single':>12}")
    print("-" * 60)
    n_unlock_motivation = 0; n_unlock_holdout = 0
    for r in results:
        tid = r["id"]; v81_pass = r["hard"] == "PASS"
        kind = "MOTIVATION" if tid in MOTIVATION else "HOLDOUT"
        v8_runs = v8_per_task.get(tid, [])
        v8_str = f"{sum(v8_runs)}/{len(v8_runs)}"
        print(f"{tid:>8} | {kind:>10} | {v8_str:>13} | {r['hard']:>10} cell={r['cell']:.0%}")
        if v81_pass:
            if tid in MOTIVATION: n_unlock_motivation += 1
            else: n_unlock_holdout += 1

    print(f"\nUnlock counts: motivation {n_unlock_motivation}/{len(MOTIVATION)}, hold-out {n_unlock_holdout}/{len(HOLDOUT)}")
    pass_criteria = (n_unlock_motivation >= 2 and n_unlock_holdout >= 1)
    if pass_criteria:
        verdict = "PASS — proceed to v8.1 multi-seed full eval"
    elif n_unlock_motivation >= 1:
        verdict = "PARTIAL — some unlock but below threshold; investigate before full eval"
    else:
        verdict = "FAIL — append-rules approach didn't help. STOP."
    print(f"\nVerdict: {verdict}")
    print(f"Cost: ${cost.total_cost:.3f}")

    Path("results/runs/g2b-v8_1_gpt-5.4_5task_test/summary.json").write_text(
        json.dumps({"results": results, "n_unlock_motivation": n_unlock_motivation,
                    "n_unlock_holdout": n_unlock_holdout, "verdict": verdict,
                    "cost": cost.total_cost}, indent=2))


if __name__ == "__main__":
    asyncio.run(main_async())
