#!/usr/bin/env python3
"""Mechanism ablation: replay A5 seed 1 iter 8 patcher with/without adherence block.

Compares output (which patches proposed) under 2 conditions:
  - CONTROL: full query including adherence block (= original A5 iter 8)
  - ABLATION: same query, adherence block stripped

If CONTROL adds 0 new H2 (matching A5 final) and ABLATION adds 4 H2 (matching A0 final),
the adherence prompt is the active driver. If both behave same, it's not.
"""
import asyncio
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import Agent, Runner
from pipeline.helpers import _build_file_tools, _resolve_model
from pipeline.group_patcher import _build_adherence_block
from runners.cost_tracker import CostTracker
from runners.model_settings import get_model_settings
from runners.trajectory_logger import TrajectoryLogger, stream_with_logging

# Read patcher prompt
import importlib.util
spec = importlib.util.spec_from_file_location("group_patcher_prompts",
    "prompts/group_patcher.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
PROMPT = m.GROUP_PATCHER_PROMPT

ITER8 = Path("results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed1/train/iter_8")
SKILLS_DIR = Path("results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed1/skills")
PROJECT_ROOT = Path(".").resolve()


async def run_one_replay(condition: str, include_adherence: bool):
    cards = ITER8 / "batch_diagnostic_cards.md"
    overlay = ITER8 / "momentum_overlay.md"
    record = ITER8 / "momentum_memory.md"
    pending = Path("results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed1/train/pending_pool.md")
    adh_path = ITER8 / "adherence_summary.md" if include_adherence else None

    skill_dir = SKILLS_DIR / "xlsx"
    skill_files = [str(skill_dir / "SKILL.md")]
    refs_dir = skill_dir / "references"
    if refs_dir.exists():
        for f in sorted(refs_dir.iterdir()):
            if f.is_file(): skill_files.append(str(f))

    query = (
        f"This is iteration 8 (ABLATION REPLAY - {condition}).\n\n"
        f"## Inputs\n"
        f"- Group cards: {cards}\n"
        f"- Overlay:     {overlay}\n"
        f"- Pattern record: {record}\n"
        f"- Pending pool:   {pending}\n"
        f"- Current skill files:\n"
        + "\n".join(f"    - {p}" for p in skill_files) + "\n"
        f"- Reference dir for new L3 files: {refs_dir}\n"
        f"  (Create files there for new L3 chapters; may not exist yet.)\n\n"
        f"## Outputs you must write\n"
        f"NOTE: this is an ABLATION REPLAY — do NOT actually write files; just\n"
        f"output your routing decisions table + patch actions summary in your\n"
        f"final message. Do not call write_file.\n\n"
        f"For inspectable patterns, run the §3a routing table.\n"
    )
    query += _build_adherence_block(adh_path)

    read_file, _write_file = _build_file_tools(PROJECT_ROOT)
    cost_tracker = CostTracker(model="gpt-4.1")
    out_log = ITER8.parent.parent.parent / f"ablation_{condition}.jsonl"
    logger = TrajectoryLogger(out_log)
    agent = Agent(
        name="GroupPatcher",
        instructions=PROMPT,
        model=_resolve_model("gpt-4.1"),
        model_settings=get_model_settings("gpt-4.1"),
        tools=[read_file],  # read-only for ablation
    )
    result = Runner.run_streamed(agent, query, max_turns=25)
    await stream_with_logging(result, logger)
    cost_tracker.update(result)
    return result.final_output or "", out_log


async def main():
    print("=== CONTROL (with adherence) ===")
    out_ctrl, _ = await run_one_replay("CONTROL_with_adh", include_adherence=True)
    Path("results/ablation_control.md").write_text(out_ctrl)
    print(f"  saved to results/ablation_control.md ({len(out_ctrl)} chars)")

    print("\n=== ABLATION (no adherence) ===")
    out_abl, _ = await run_one_replay("ABLATION_no_adh", include_adherence=False)
    Path("results/ablation_no_adh.md").write_text(out_abl)
    print(f"  saved to results/ablation_no_adh.md ({len(out_abl)} chars)")


if __name__ == "__main__":
    asyncio.run(main())
