"""Bench-agnostic execution primitives.

After A7 refactor (G2B-Skill 2026-06-16), the bench-specific functions
(``load_dataset``, ``build_task_string``, ``build_ground_truth_text``,
``prepare_seed_data``, ``assess_seed``) live as methods on Bench
implementations under ``bench/``. Use ``bench.get_bench(name, ...)``
to obtain a Bench, then call its methods directly.

This module keeps only the two pieces that are genuinely
bench-agnostic:

  - ``_write_workspace``: small JSON/text writer used everywhere.
  - ``run_execute``: drives the SkillAgent on a pre-prepared seed_data.

The seed_data dict shape (constructed by ``Bench.prepare_seed_data``)
is what makes this bench-agnostic — ``run_execute`` only reads
``seed_data["task_str"]`` and ``seed_data["task_workdir"]``.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from agents import Runner

from pipeline.executor import SkillAgent
from prompts.executor import EXECUTOR_PROMPT
from runners.cost_tracker import CostTracker
from runners.model_settings import get_model_kwargs
from runners.trajectory_logger import (
    TrajectoryLogger,
    set_phase,
    stream_with_logging,
)


def _write_workspace(path: Path, data: dict | str) -> None:
    """Write a JSON or text artifact to the shared workspace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )


async def run_execute(
    seed_data: dict,
    semaphore: asyncio.Semaphore,
    skills_dir: Path,
    model: str,
    project_root: Path,
    max_turns: int,
    round_num: int,
    cost_tracker: CostTracker,
    openai_client=None,
    skill_name: str = "xlsx",
    temperature: float | None = None,
) -> dict:
    """Execute ONE seed with SkillAgent.

    Bench-agnostic: relies only on ``seed_data["task_str"]`` and
    ``seed_data["task_workdir"]``. Pass ``skill_name`` to scope the
    executor to the right skill (defaults to ``"xlsx"`` for backwards
    compatibility with SkillGrad-style spreadsheet runs).

    ``temperature`` is forwarded into the executor's ``ModelSettings``.
    Group-rollout callers raise this above the proxy default to widen
    contrastive variance across rollouts.
    """
    async with semaphore:
        idx = seed_data["index"]
        ex_id = seed_data["id"]
        task_str = seed_data["task_str"]
        task_workdir = seed_data["task_workdir"]

        print(f"\n  [exec] Starting seed {idx} (id={ex_id}) round={round_num}")
        model_kwargs = get_model_kwargs(model, openai_client=openai_client,
                                        temperature=temperature)

        log_path = task_workdir / f"exec_r{round_num}.jsonl"
        logger = TrajectoryLogger(log_path)
        set_phase("EXECUTE", logger)

        executor = SkillAgent(
            skills_dir=skills_dir,
            model=model,
            max_turns=max_turns,
            system_prompt=EXECUTOR_PROMPT,
            model_kwargs=model_kwargs,
            include_skills=[skill_name],
            project_root=project_root,
        )

        t0 = time.time()
        executor_output = ""
        try:
            result = Runner.run_streamed(
                executor.agent, task_str, max_turns=max_turns,
            )
            await stream_with_logging(result, logger)
            executor_output = result.final_output or ""
            delta = cost_tracker.update(result)
            cost_tracker.print_step(f"EXEC seed={idx} r{round_num}", delta)
        except Exception as e:
            print(f"  [exec] Seed {idx} EXECUTE error: {e}")
            executor_output = f"[EXECUTION ERROR] {e}"

        logger.flush()
        elapsed = round(time.time() - t0, 2)

        return {
            "index": idx,
            "id": ex_id,
            "executor_output": executor_output,
            "elapsed": elapsed,
            "trajectory_path": str(log_path),
            "logger": logger,
            "task_workdir": str(task_workdir),
        }
