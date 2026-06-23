"""Test MIXED_GROUP_K_TRACE_PROMPT on real v7 mixed-group data.

Cases:
  - iter_1/142-19 (1 PASS r0=100%, 3 FAIL r1=6% r2=40% r3=40%) — clean contrast
  - iter_5/9111 (mixed)
  - iter_6/53117 (mixed)
"""
import asyncio, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"

from agents import Agent, Runner

from pipeline.helpers import _build_file_tools, _resolve_model
from prompts.v8_diagnoser import MIXED_GROUP_K_TRACE_PROMPT
from runners.cost_tracker import CostTracker
from runners.model_settings import get_model_settings

V7_TRAIN = Path("results/runs/g2b-v7_gpt-5.4/train")
CASES = [(1, "142-19", 4), (5, "9111", 4), (6, "53117", 4)]


def get_task_instruction(tid):
    ds = json.load(open("data/benchmarks/spreadsheetbench/dataset.json"))
    return next(t["instruction"] for t in ds if str(t["id"]) == tid)


def get_per_rollout_outcomes(iter_num, tid, K):
    out = []
    for k in range(K):
        a = json.loads((V7_TRAIN / f"iter_{iter_num}" / f"task_{tid}" / f"r{k}" /
                        f"evolve_{tid}" / f"assessment_r{k}.json").read_text())
        verdict = "PASS" if a["is_correct"] else "FAIL"
        out.append((k, verdict, a["accuracy"], a["match_count"], a["total_count"]))
    return out


def build_query(iter_num, tid, K):
    task = get_task_instruction(tid)
    outcomes = get_per_rollout_outcomes(iter_num, tid, K)
    # find a failed rollout for cell comparison
    fail_k = next((k for k, v, *_ in outcomes if v == "FAIL"), 0)
    fail_a = json.loads((V7_TRAIN / f"iter_{iter_num}" / f"task_{tid}" / f"r{fail_k}" /
                        f"evolve_{tid}" / f"assessment_r{fail_k}.json").read_text())
    cc = (f"r{fail_k} cell accuracy: {fail_a['match_count']}/{fail_a['total_count']} "
          f"({fail_a['accuracy']:.0%})")

    trace_lines = []
    for k, verdict, acc, *_ in outcomes:
        path = V7_TRAIN / f"iter_{iter_num}" / f"task_{tid}" / f"r{k}" / f"evolve_{tid}" / f"exec_r{k}.jsonl"
        trace_lines.append(f"  - r{k} ({verdict}, cell {acc:.0%}): {path}")

    return (
        f"## Task\n{task}\n\n"
        f"## Cell comparison (representative, from rollout {fail_k} which FAILED)\n{cc}\n\n"
        f"## Files (read all K with read_file)\n"
        + "\n".join(trace_lines)
        + f"\n  - Skill directory: results/runs/g2b-v7_gpt-5.4/train/snapshot_iter_{iter_num}/xlsx\n"
    )


async def test_one(iter_num, tid, K):
    print(f"\n{'='*70}\n=== iter_{iter_num} / task {tid} (mixed K={K}) ===\n{'='*70}\n")
    cost = CostTracker("gpt-5.4")
    read_file, _ = _build_file_tools(Path(".").resolve())
    agent = Agent(name=f"MixDiag-{tid}", instructions=MIXED_GROUP_K_TRACE_PROMPT,
                  model=_resolve_model("gpt-5.4"), model_settings=get_model_settings("gpt-5.4"),
                  tools=[read_file])
    query = build_query(iter_num, tid, K)
    result = Runner.run_streamed(agent, query, max_turns=15)
    async for _ in result.stream_events(): pass
    cost.update(result)
    out = result.final_output or ""
    print(out)
    print(f"\n--- ${cost.total_cost:.3f} ---")
    return {"iter": iter_num, "task": tid, "output": out, "cost": cost.total_cost}


async def main():
    rs = []
    for iter_num, tid, K in CASES:
        rs.append(await test_one(iter_num, tid, K))
    print(f"\n{'='*70}\n=== SUMMARY ===\n{'='*70}")
    for r in rs:
        label = next((l.replace("LABEL:","").strip() for l in r["output"].split("\n")
                     if l.strip().startswith("LABEL:")), "?")
        print(f"  iter_{r['iter']}/task {r['task']}: LABEL={label}, ${r['cost']:.3f}")
    print(f"Total: ${sum(r['cost'] for r in rs):.3f}")


if __name__ == "__main__":
    asyncio.run(main())
