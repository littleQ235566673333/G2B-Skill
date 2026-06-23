"""Skill patch stage.

The patcher reads the current task evidence, optional momentum overlay, and
current skill files. It evolves the skill in place by writing new content via
the write_file tool. In the current pipeline every patch is accepted; skill
snapshots are kept for forensics.
"""

import time
from pathlib import Path
from typing import Optional

from agents import Agent, Runner

from pipeline.helpers import _build_file_tools, _resolve_model
from prompts.patcher import PATCHER_PROMPT
from runners.cost_tracker import CostTracker
from runners.model_settings import get_model_settings
from runners.trajectory_logger import TrajectoryLogger, stream_with_logging


async def run_patch(
    batch_diagnoses_path: Path,
    skills_dir: Path,
    model: str,
    project_root: Path,
    cost_tracker: CostTracker,
    iter_dir: Path,
    overlay_path: Optional[Path] = None,
    momentum_memory_path: Optional[Path] = None,
    group_evidence_path: Optional[Path] = None,
    skill_name: str = "xlsx",
) -> str:
    """Run the patcher agent to evolve the skill.

    ``group_evidence_path`` (v7 additive extension): optional path to a markdown
    file containing per-task K-rollout group evidence. If provided, the patcher
    is instructed to read it as additional evidence for skill evolution. The
    SkillGrad PATCHER_PROMPT itself is unchanged — group evidence is purely an
    additive input to the user message.

    ``skill_name`` (2026-06-19 fix): name of the skill subdir under ``skills_dir``.
    Defaults to "xlsx" for backward compat. Pass bench.skill_name (e.g., "wtq")
    when training on benches other than spreadsheet, or the patcher will write to
    the wrong subdirectory and final_skill capture will return seed.
    """
    read_file, write_file = _build_file_tools(project_root)

    agent = Agent(
        name="Patcher",
        instructions=PATCHER_PROMPT,
        model=_resolve_model(model),
        model_settings=get_model_settings(model),
        tools=[read_file, write_file],
    )

    # List actual files so the agent doesn't guess filenames
    skill_dir = skills_dir / skill_name
    skill_files = [str(skill_dir / "SKILL.md")]
    refs_dir = skill_dir / "references"
    if refs_dir.exists():
        for f in sorted(refs_dir.iterdir()):
            if f.is_file():
                skill_files.append(str(f))

    query = (
        f"Evolve the skill based on the analysis below.\n\n"
        f"Original diagnoses: {batch_diagnoses_path}\n"
    )
    if overlay_path is not None:
        query += f"Per-attempt overlay: {overlay_path}\n"
    if momentum_memory_path is not None:
        query += f"Cross-iteration pattern record: {momentum_memory_path}\n"
    if group_evidence_path is not None:
        query += (
            f"K-rollout group evidence (per-task contrastive within same skill version): "
            f"{group_evidence_path}\n"
            f"  (Each task in this batch was rolled out K times under the current skill. "
            f"This file lists, per task, which rollouts succeeded vs failed and what "
            f"behavioral divergence separated them. Use it as same-skill same-task "
            f"contrastive evidence in addition to the diagnoses above.)\n"
        )
    query += (
        f"Skill files:\n"
        + "\n".join(f"  - {p}" for p in skill_files)
        + "\n"
        f"Reference directory for new L3 files: {refs_dir}\n"
        f"(Create files there when a reusable procedure should live outside "
        f"`SKILL.md`; it may not exist yet.)\n"
        f"\n"
        f"CRITICAL — INCREMENTAL EDITS ONLY:\n"
        f"  Read the current SKILL.md FIRST. Then make INCREMENTAL edits — "
        f"add new H2 sections, append bullets, refine existing sentences. "
        f"NEVER replace the entire SKILL.md with a rewritten version. "
        f"NEVER delete >30% of the existing content in a single edit. "
        f"If the current SKILL.md has accumulated knowledge, that knowledge "
        f"is valuable — preserve it and ADD on top, do not start over.\n"
    )

    logger = TrajectoryLogger(iter_dir / "patcher.jsonl")
    print(f"  [patch] Evolving skill")
    t0 = time.time()
    output = ""
    try:
        result = Runner.run_streamed(agent, query, max_turns=20)
        await stream_with_logging(result, logger)
        output = result.final_output or ""
        delta = cost_tracker.update(result)
        cost_tracker.print_step("PATCH", delta)
    except Exception as e:
        print(f"  [patch] error: {e}")
        output = f"[PATCH ERROR] {e}"
    logger.flush()
    elapsed = round(time.time() - t0, 2)
    print(f"  [patch] Done in {elapsed}s")

    return output
