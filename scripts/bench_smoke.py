"""Generic 1-task smoke test: bench name → 1 task → seed skill → executor → assess.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/bench_smoke.py <bench>

Where <bench> is one of: searchqa | livemath | officeqa.

Checks the same end-to-end loop as scripts/searchqa_smoke.py but works for
any bench registered in bench/__init__.py.
"""

import asyncio
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"

from bench import get_bench
from pipeline.execution import run_execute
from runners.cost_tracker import CostTracker
from runners.model_dispatch import get_client_for_model

MODEL = "gpt-5.4"

DEFAULT_DATA_DIRS = {
    "searchqa": "data/benchmarks/searchqa",
    "livemath": "data/benchmarks/livemathbench",
    "officeqa": "data/benchmarks/officeqa",
}


async def main_async(bench_name: str, idx: int = 0) -> None:
    project_root = Path(".").resolve()
    workdir = Path(f"results/runs/{bench_name}_smoke")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    bench = get_bench(bench_name, data_dir=DEFAULT_DATA_DIRS[bench_name])

    skills_dir = workdir / "skills"
    skill_dest = skills_dir / bench.skill_name
    skill_dest.mkdir(parents=True)
    seed_md = Path(f"seeds/{bench.skill_name}/SKILL.md")
    if not seed_md.exists():
        sys.exit(f"missing seed: {seed_md}")
    shutil.copy2(seed_md, skill_dest / "SKILL.md")
    print(f"Seeded skill: {skill_dest / 'SKILL.md'} "
          f"({(skill_dest / 'SKILL.md').stat().st_size} bytes)")

    dataset = bench.load_dataset()
    print(f"Dataset loaded: {len(dataset)} entries")

    seed_data = bench.prepare_seed_data(dataset, idx, workdir / "iter_smoke")
    print(f"Task {idx} id={seed_data['id']}")
    print(f"  Question (truncated): {seed_data['example']['instruction'][:160]}...")
    print(f"  Workdir: {seed_data['task_workdir']}")

    cost = CostTracker(MODEL)
    sem = asyncio.Semaphore(2)
    client = get_client_for_model(MODEL)

    print(f"\n── EXECUTE ──")
    exec_result = await run_execute(
        seed_data=seed_data,
        semaphore=sem,
        skills_dir=skills_dir,
        model=MODEL,
        project_root=project_root,
        max_turns=30,
        round_num=0,
        cost_tracker=cost,
        openai_client=client,
        skill_name=bench.skill_name,
    )

    print(f"\n── ASSESS ──")
    assessment = bench.assess(seed_data, exec_result, round_num=0)

    out_path = seed_data["task_workdir"] / "output.txt"
    out_text = out_path.read_text(encoding="utf-8") if out_path.exists() else "<missing>"

    print(f"\n=== RESULT ===")
    print(f"  Predicted output.txt: {out_text[:300]!r}")
    print(f"  accuracy={assessment['accuracy']['accuracy']}")
    if "em" in assessment["accuracy"]:
        print(f"  EM={assessment['accuracy']['em']}, F1={assessment['accuracy'].get('f1', 0):.3f}")
    if "judge_verdict" in assessment["accuracy"]:
        print(f"  judge_verdict={assessment['accuracy']['judge_verdict']}")
    if "match_type" in assessment["accuracy"]:
        print(f"  match_type={assessment['accuracy']['match_type']}")
    print(f"  PASS: {assessment['is_correct']}")
    print(f"  Cost: ${cost.total_cost:.3f}")


if __name__ == "__main__":
    bench_name = sys.argv[1] if len(sys.argv) > 1 else "searchqa"
    if bench_name not in DEFAULT_DATA_DIRS:
        sys.exit(f"unknown bench: {bench_name}; choose from {list(DEFAULT_DATA_DIRS)}")
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    asyncio.run(main_async(bench_name, idx))
