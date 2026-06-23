"""Group momentum stage (Phase 3).

Reads the current iteration's group diagnostic cards, the previous iteration's
pattern record, and current skill files; writes:

  - an updated pattern record (`momentum_memory.md`) carrying:
      * evidence_profile per pattern (mixed/all_fail/all_success counters)
      * peak_strength + current_strength derived fields
      * remedy_log rows tagged with `group=<type>`
  - a per-group overlay (`momentum_overlay.md`) with three branch-specific
    schemas (mixed / all_fail / all_success) plus `## WORKFLOW-THEMES`
    derived strictly from mixed-group entries.

Schema details + hard constraints live in `prompts/group_momentum.py`. This
runner is a thin async wrapper that surfaces the file paths to the LLM.

SkillGrad's original `pipeline/momentum.py` (single-trajectory baseline) is
unchanged — it stays available for K=1 ablation.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from agents import Agent, Runner

from pipeline.helpers import _build_file_tools, _resolve_model
from prompts.group_momentum import GROUP_MOMENTUM_PROMPT
from runners.cost_tracker import CostTracker
from runners.model_settings import get_model_settings
from runners.trajectory_logger import TrajectoryLogger, stream_with_logging


async def run_group_momentum(
    cards_path: Path,
    previous_record_path: Path,
    skills_dir: Path,
    skill_name: str,
    record_output_path: Path,
    overlay_output_path: Path,
    model: str,
    project_root: Path,
    cost_tracker: CostTracker,
    iter_dir: Path,
    iter_num: int,
) -> None:
    """Run the group-aware pattern-record writer for one iteration.

    Args:
        cards_path: ``batch_diagnostic_cards.md`` from Phase 2 (assembled
            via ``pipeline.group_diagnoser.assemble_group_cards``).
        previous_record_path: previous iteration's ``momentum_memory.md``.
            Empty placeholder OK on iter 1.
        skills_dir: parent of the skill directory; ``skills_dir /
            skill_name / SKILL.md`` is the L2 file.
        skill_name: e.g. ``"xlsx"`` or ``"wtq"`` — bench-specific.
        record_output_path: where to write the updated pattern record.
        overlay_output_path: where to write the per-group overlay.
        iter_num: 1-indexed iteration number.

    Raises nothing; on agent error, writes minimal placeholder files so
    the downstream patcher (Phase 4) can still proceed. Always flushes
    the trajectory log.
    """
    read_file, write_file = _build_file_tools(project_root)

    agent = Agent(
        name="GroupPatternRecordWriter",
        instructions=GROUP_MOMENTUM_PROMPT,
        model=_resolve_model(model),
        model_settings=get_model_settings(model),
        tools=[read_file, write_file],
    )

    # Surface skill file paths so the agent doesn't guess filenames.
    skill_dir = skills_dir / skill_name
    skill_files = [str(skill_dir / "SKILL.md")]
    refs_dir = skill_dir / "references"
    if refs_dir.exists():
        for f in sorted(refs_dir.iterdir()):
            if f.is_file():
                skill_files.append(str(f))

    query = (
        f"This is iteration {iter_num}.\n\n"
        f"Read the input files and write your two outputs to the paths below.\n\n"
        f"Inputs:\n"
        f"  Current iteration's group diagnostic cards: {cards_path}\n"
        f"  Previous iteration's pattern record: {previous_record_path}\n"
        f"  Current guidance files:\n"
        + "\n".join(f"    - {p}" for p in skill_files)
        + "\n\n"
        f"Outputs:\n"
        f"  Updated pattern record: {record_output_path}\n"
        f"  Per-group overlay:      {overlay_output_path}\n"
    )

    logger = TrajectoryLogger(iter_dir / "group_momentum.jsonl")
    print(f"  [group_momentum] iter {iter_num}: synthesizing pattern record + overlay")
    t0 = time.time()
    try:
        result = Runner.run_streamed(agent, query, max_turns=20)
        await stream_with_logging(result, logger)
        delta = cost_tracker.update(result)
        cost_tracker.print_step("GROUP_MOMENTUM", delta)
    except Exception as e:
        print(f"  [group_momentum] error: {e}")
        # Fallback: write minimal record + overlay so downstream doesn't crash.
        if not record_output_path.exists():
            record_output_path.write_text(
                f"# Pattern record (after iter {iter_num})\n\n"
                f"(GroupPatternRecordWriter failed: {e})\n",
                encoding="utf-8",
            )
        if not overlay_output_path.exists():
            overlay_output_path.write_text(
                f"# Per-group overlay (iter {iter_num})\n\n"
                f"(GroupPatternRecordWriter failed: {e}; "
                f"patcher should read the cards directly.)\n",
                encoding="utf-8",
            )
    logger.flush()
    elapsed = round(time.time() - t0, 2)
    print(f"  [group_momentum] Done in {elapsed}s")
