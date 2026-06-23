"""Minimal SearchQA smoke test: 1 task, seed skill, gpt-5.4.

Checks:
  1. bench.load_dataset() works
  2. bench.prepare_seed_data() materializes input.txt + correct task_str
  3. run_execute() drives SkillAgent over 1 task with seeds/searchqa skill
  4. bench.assess() reads output.txt and scores EM/F1

Usage:
    PYTHONPATH=. .venv/bin/python scripts/searchqa_smoke.py
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


async def main_async() -> None:
    project_root = Path(".").resolve()
    workdir = Path("results/runs/searchqa_smoke")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    # Stage seed skill into workdir/skills/searchqa (executor needs it on disk)
    skills_dir = workdir / "skills"
    skill_dest = skills_dir / "searchqa"
    skill_dest.mkdir(parents=True)
    shutil.copy2(Path("seeds/searchqa/SKILL.md"), skill_dest / "SKILL.md")
    print(f"Seeded skill: {skill_dest / 'SKILL.md'} "
          f"({(skill_dest / 'SKILL.md').stat().st_size} bytes)")

    bench = get_bench("searchqa", data_dir="data/benchmarks/searchqa")
    dataset = bench.load_dataset()
    print(f"Dataset loaded: {len(dataset)} entries")

    # Pick task 0 (deterministic)
    idx = 0
    seed_data = bench.prepare_seed_data(dataset, idx, workdir / "iter_smoke")
    print(f"Task 0 id={seed_data['id']}")
    print(f"  Question: {seed_data['example']['instruction']}")
    print(f"  Gold:     {seed_data['example']['answer_values']}")
    print(f"  Workdir:  {seed_data['task_workdir']}")
    print(f"  Input:    {(seed_data['task_workdir'] / 'input.txt').stat().st_size} bytes")

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
        max_turns=20,
        round_num=0,
        cost_tracker=cost,
        openai_client=client,
        skill_name="searchqa",
    )

    print(f"\n── ASSESS ──")
    assessment = bench.assess(seed_data, exec_result, round_num=0)
    print(f"\n=== RESULT ===")
    print(f"  Predicted output.txt: "
          f"{(seed_data['task_workdir'] / 'output.txt').read_text(encoding='utf-8') if (seed_data['task_workdir'] / 'output.txt').exists() else '<missing>'}")
    print(f"  EM:  {assessment['accuracy']['em']}")
    print(f"  F1:  {assessment['accuracy']['f1']:.3f}")
    print(f"  PASS: {assessment['is_correct']}")
    print(f"  Cost: ${cost.total_cost:.3f}")


if __name__ == "__main__":
    asyncio.run(main_async())
