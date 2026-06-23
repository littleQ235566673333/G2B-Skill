"""v8 group-aware diagnose functions.

Three diagnose flavors mapped to v8's three group states:

  group_type      | diagnose function                          | input
  ----------------|--------------------------------------------|---------------------------
  mixed           | run_mixed_group_k_trace_diagnose           | K assessments (PASS+FAIL)
  all_fail        | run_all_fail_cluster_diagnose              | K assessments (all FAIL)
  all_success     | (delegate to SkillGrad run_diagnose         | r0 assessment (cross-version
                  |  with diagnosis_type="contrastive")         |  vs base)

SkillGrad's pipeline/diagnoser.py is unchanged. This module adds the two new
diagnose entry points; the v8 training loop dispatches based on group_type.
"""
from __future__ import annotations
import asyncio, time
from pathlib import Path

from agents import Agent, Runner

from pipeline.execution import _write_workspace
from pipeline.diagnoser import _extract_diagnosis
from pipeline.helpers import _build_file_tools, _resolve_model
from prompts.v8_diagnoser import ALL_FAIL_CLUSTERING_PROMPT, MIXED_GROUP_K_TRACE_PROMPT
from runners.cost_tracker import CostTracker
from runners.model_settings import get_model_settings
from runners.trajectory_logger import TrajectoryLogger, save_merged_trace, stream_with_logging


def _build_k_trace_query(
    task_instruction: str,
    group_assessments: list[dict],
    skill_dir: Path,
    *,
    representative_fail_idx: int,
) -> str:
    """Build a K-trace query for mixed_group or all_fail diagnosers."""
    cell_comp = "(cell comparison not present in assessment)"
    rep = group_assessments[representative_fail_idx]
    if "cell_comparison" in rep:
        cell_comp = rep["cell_comparison"]
    elif "match_count" in rep and "total_count" in rep:
        cell_comp = (f"r{rep.get('_rollout_idx', representative_fail_idx)} "
                     f"cell accuracy: {rep['match_count']}/{rep['total_count']} "
                     f"({rep.get('accuracy', {}).get('accuracy', 0) if isinstance(rep.get('accuracy'), dict) else rep.get('accuracy', 0):.0%})")

    trace_lines = []
    for a in sorted(group_assessments, key=lambda x: x.get("_rollout_idx", 0)):
        k = a.get("_rollout_idx", "?")
        verdict = "PASS" if a["is_correct"] else "FAIL"
        acc = a.get("accuracy", {}).get("accuracy", 0) if isinstance(a.get("accuracy"), dict) else a.get("accuracy", 0)
        traj = a.get("trajectory_path", "")
        trace_lines.append(f"  - r{k} ({verdict}, cell {acc:.0%}): {traj}")

    return (
        f"## Task\n{task_instruction}\n\n"
        f"## Cell comparison (representative, from a FAILED rollout)\n{cell_comp}\n\n"
        f"## Files (read all K with read_file)\n"
        + "\n".join(trace_lines)
        + f"\n  - Skill directory: {skill_dir}\n"
    )


async def run_mixed_group_k_trace_diagnose(
    group_assessments: list[dict],
    iter_dir: Path,
    skills_dir: Path,
    model: str,
    project_root: Path,
    semaphore: asyncio.Semaphore,
    cost_tracker: CostTracker,
    skill_name: str = "xlsx",
) -> dict:
    """Run K-trace contrastive diagnosis on a mixed group (some PASS, some FAIL).

    Output is compatible with assemble_diagnoses (same dict shape as
    SkillGrad's run_diagnose returns).
    """
    async with semaphore:
        ex_id = group_assessments[0]["id"]
        # Pick representative fail rollout for cell_comparison
        fail_idx = next(
            (i for i, a in enumerate(group_assessments) if not a["is_correct"]), 0
        )
        # Ensure each assessment has trajectory_path populated; if not, derive
        for a in group_assessments:
            if "trajectory_path" not in a or not a["trajectory_path"]:
                wd = a.get("task_workdir", "")
                k = a.get("_rollout_idx", 0)
                if wd:
                    a["trajectory_path"] = str(Path(wd) / f"exec_r{k}.jsonl")

        # Build query
        task_instruction = group_assessments[0].get("example", {}).get("instruction", "(missing instruction)")
        query = _build_k_trace_query(
            task_instruction, group_assessments,
            skills_dir / skill_name, representative_fail_idx=fail_idx,
        )

        # Build agent
        read_file, _ = _build_file_tools(project_root)
        agent = Agent(
            name=f"MixedDiag-{ex_id}",
            instructions=MIXED_GROUP_K_TRACE_PROMPT,
            model=_resolve_model(model),
            model_settings=get_model_settings(model),
            tools=[read_file],
        )
        diag_dir = iter_dir / f"diagnose_{ex_id}"
        diag_dir.mkdir(parents=True, exist_ok=True)
        logger = TrajectoryLogger(diag_dir / "diagnosis.jsonl")

        print(f"  [diagnose] mixed-K-trace for {ex_id}")
        t0 = time.time()
        try:
            result = Runner.run_streamed(agent, query, max_turns=15)
            await stream_with_logging(result, logger)
            output = result.final_output or ""
            delta = cost_tracker.update(result)
            cost_tracker.print_step(f"DIAGNOSE-MIXED {ex_id}", delta)
        except Exception as e:
            print(f"  [diagnose] {ex_id} mixed error: {e}")
            output = f"[DIAGNOSIS ERROR] {e}"
        logger.flush()

        diagnosis_text = _extract_diagnosis(output)
        _write_workspace(diag_dir / "diagnosis.txt", diagnosis_text)
        return {
            "id": ex_id, "type": "mixed_group_k_trace",
            "diagnosis": diagnosis_text,
            "elapsed": round(time.time() - t0, 2),
        }


async def run_all_fail_cluster_diagnose(
    group_assessments: list[dict],
    iter_dir: Path,
    skills_dir: Path,
    model: str,
    project_root: Path,
    semaphore: asyncio.Semaphore,
    cost_tracker: CostTracker,
    skill_name: str = "xlsx",
) -> dict:
    """Run K-trace clustering diagnosis on an all_fail group (all K rollouts FAIL).

    Classifies convergent vs divergent and produces a single diagnosis tailored
    to which case applies.
    """
    async with semaphore:
        ex_id = group_assessments[0]["id"]
        for a in group_assessments:
            if "trajectory_path" not in a or not a["trajectory_path"]:
                wd = a.get("task_workdir", "")
                k = a.get("_rollout_idx", 0)
                if wd:
                    a["trajectory_path"] = str(Path(wd) / f"exec_r{k}.jsonl")

        task_instruction = group_assessments[0].get("example", {}).get("instruction", "(missing instruction)")
        query = _build_k_trace_query(
            task_instruction, group_assessments,
            skills_dir / skill_name, representative_fail_idx=0,
        )

        read_file, _ = _build_file_tools(project_root)
        agent = Agent(
            name=f"AllFailDiag-{ex_id}",
            instructions=ALL_FAIL_CLUSTERING_PROMPT,
            model=_resolve_model(model),
            model_settings=get_model_settings(model),
            tools=[read_file],
        )
        diag_dir = iter_dir / f"diagnose_{ex_id}"
        diag_dir.mkdir(parents=True, exist_ok=True)
        logger = TrajectoryLogger(diag_dir / "diagnosis.jsonl")

        print(f"  [diagnose] all-fail-cluster for {ex_id}")
        t0 = time.time()
        try:
            result = Runner.run_streamed(agent, query, max_turns=15)
            await stream_with_logging(result, logger)
            output = result.final_output or ""
            delta = cost_tracker.update(result)
            cost_tracker.print_step(f"DIAGNOSE-ALLFAIL {ex_id}", delta)
        except Exception as e:
            print(f"  [diagnose] {ex_id} all_fail error: {e}")
            output = f"[DIAGNOSIS ERROR] {e}"
        logger.flush()

        diagnosis_text = _extract_diagnosis(output)
        _write_workspace(diag_dir / "diagnosis.txt", diagnosis_text)
        return {
            "id": ex_id, "type": "all_fail_cluster",
            "diagnosis": diagnosis_text,
            "elapsed": round(time.time() - t0, 2),
        }
