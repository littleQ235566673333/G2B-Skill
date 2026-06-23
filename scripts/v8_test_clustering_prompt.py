"""Standalone test of ALL_FAIL_CLUSTERING_PROMPT before wiring it into v8 training.

Test cases: 3 all_fail groups from v7's iter_1 / iter_2 to check prompt robustness:
  - 160-6 (iter_1, VBA macro task)
  - 194-19 (iter_2)
  - 32023 (iter_2)

Output: prints diagnosis for each, lets us eyeball quality before training.
"""
import asyncio, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"

from agents import Agent, Runner

from pipeline.helpers import _build_file_tools, _resolve_model
from prompts.v8_diagnoser import ALL_FAIL_CLUSTERING_PROMPT
from runners.cost_tracker import CostTracker
from runners.model_settings import get_model_settings

V7_TRAIN = Path("results/runs/g2b-v7_gpt-5.4/train")

# (iter, task_id, K)
CASES = [
    (1, "160-6", 4),
    (2, "194-19", 4),
    (2, "32023", 4),
]


def get_task_instruction(tid):
    ds = json.load(open("data/benchmarks/spreadsheetbench/dataset.json"))
    for t in ds:
        if str(t["id"]) == tid:
            return t["instruction"]
    raise ValueError(f"task {tid} not found")


def get_cell_comparison_str(iter_num, tid):
    """Build a cell_comparison-like summary from r0's assessment."""
    a_path = V7_TRAIN / f"iter_{iter_num}" / f"task_{tid}" / "r0" / f"evolve_{tid}" / "assessment_r0.json"
    if not a_path.exists():
        return "(cell comparison not available)"
    a = json.loads(a_path.read_text())
    return (f"r0 cell accuracy: {a.get('match_count','?')}/{a.get('total_count','?')} "
            f"({a.get('accuracy', 0):.0%}); is_correct={a.get('is_correct')}")


def build_k_trace_query(iter_num, tid, K):
    task_desc = get_task_instruction(tid)
    cell_comp = get_cell_comparison_str(iter_num, tid)
    trace_lines = []
    for k in range(K):
        trace_path = V7_TRAIN / f"iter_{iter_num}" / f"task_{tid}" / f"r{k}" / f"evolve_{tid}" / f"exec_r{k}.jsonl"
        trace_lines.append(f"  - r{k} trace: {trace_path}")
    return (
        f"## Task\n{task_desc}\n\n"
        f"## Cell comparison (representative, from rollout 0)\n{cell_comp}\n\n"
        f"## Files (read each with read_file)\n"
        f"You have {K} failed-rollout traces of the same task under the same skill. "
        f"Read all of them and produce one diagnosis per the workflow.\n"
        + "\n".join(trace_lines)
        + f"\n  - Skill directory: results/runs/g2b-v7_gpt-5.4/train/snapshot_iter_{iter_num}/xlsx\n"
    )


async def test_one(iter_num, tid, K, model="gpt-5.4"):
    print(f"\n{'=' * 70}\n=== TEST: iter_{iter_num} / task {tid} / K={K} ===\n{'=' * 70}\n")
    project_root = Path(".").resolve()
    cost = CostTracker(model)
    read_file, _ = _build_file_tools(project_root)

    agent = Agent(
        name=f"K-Diagnoser-{tid}",
        instructions=ALL_FAIL_CLUSTERING_PROMPT,
        model=_resolve_model(model),
        model_settings=get_model_settings(model),
        tools=[read_file],
    )

    query = build_k_trace_query(iter_num, tid, K)
    print(f"--- Query (head) ---\n{query[:600]}...\n")

    result = Runner.run_streamed(agent, query, max_turns=15)
    async for _ in result.stream_events():
        pass
    cost.update(result)
    output = result.final_output or ""

    print(f"\n--- Output ---\n{output}\n")
    print(f"--- Cost: ${cost.total_cost:.3f} ---\n")

    return {"iter": iter_num, "task": tid, "output": output, "cost": cost.total_cost}


async def main():
    results = []
    for iter_num, tid, K in CASES:
        r = await test_one(iter_num, tid, K)
        results.append(r)

    print(f"\n{'=' * 70}\n=== SUMMARY ===\n{'=' * 70}")
    total = 0
    for r in results:
        cost = r["cost"]
        total += cost
        out = r["output"]
        # check for CASE classification
        case = "?"
        for line in out.split("\n"):
            if "CONVERGENT" in line.upper(): case = "CONVERGENT"; break
            if "DIVERGENT" in line.upper(): case = "DIVERGENT"; break
        # extract LABEL
        label = "?"
        for line in out.split("\n"):
            if line.strip().startswith("LABEL:"):
                label = line.strip().replace("LABEL:", "").strip(); break
        print(f"  iter_{r['iter']}/task {r['task']}: case={case}, LABEL={label}, ${cost:.3f}")
    print(f"\nTotal cost: ${total:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
