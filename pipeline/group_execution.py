"""Group-level execution: K rollouts per task under the same skill.

Bench-aware (post-A7 refactor 2026-06-16). For each rollout, calls back
into ``bench.prepare_seed_data`` to set up an independent per-rollout
workspace, runs the executor, and uses ``bench.assess`` to score —
no spreadsheet-specific assumptions in this module.

Design notes
------------
- A "group" is K rollouts of the same task under the same skill S_t.
- Diversity injection is currently temperature-based (cheap, dirty
  baseline). Plan-level branching is the intended upgrade — see TODOs.
- Each rollout writes to ``workdir/r<k>/...`` (the bench's
  ``prepare_seed_data`` further nests under ``evolve_<id>/``).
- Classification is forward-only: count successes, return one of
  ``{"mixed", "all_fail", "all_success"}``.

Public API
----------
- run_group_execute(...)  — async; returns list[assessment] of length K
- classify_group(group_assessments) -> str
- group_advantage(group_assessments) -> list[float]   (centered reward)
- group_summary(group_assessments) -> dict
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from pipeline.execution import run_execute
from runners.cost_tracker import CostTracker

if TYPE_CHECKING:
    from bench import Bench


# ═══════════════════════════════════════════════════════════════════════════
# Group execution
# ═══════════════════════════════════════════════════════════════════════════

async def run_group_execute(
    bench: "Bench",
    dataset: list[dict],
    idx: int,
    K: int,
    workdir: Path,
    semaphore: asyncio.Semaphore,
    skills_dir: Path,
    model: str,
    project_root: Path,
    max_turns: int,
    cost_tracker: CostTracker,
    openai_client=None,
    diversity: str = "temperature",
    diversity_kwargs: Optional[dict] = None,
) -> list[dict]:
    """Run K rollouts of ``dataset[idx]`` in parallel; return K assessments.

    Each rollout gets its own workspace at ``workdir/r<k>/`` via
    ``bench.prepare_seed_data``. Concurrency is controlled by the
    caller-supplied semaphore — each rollout takes one slot.

    Returns
    -------
    list[dict]
        Length K. Each element has the shape produced by
        ``bench.assess`` (id, accuracy, is_correct, cell_comparison,
        trajectory_path, ...) plus a ``_rollout_idx`` field.

    TODO(diversity): currently the only knob is the executor's default
    temperature. To get plan-level diversity we will either (a) inject
    "produce a different plan than rollouts r<0..k-1>" into the task
    string, or (b) modify EXECUTOR_PROMPT with a plan-id parameter.
    Both interact with the contrastive diagnoser later — defer until
    mixed-group-rate pilot numbers are in.
    """
    # Set up per-rollout workspaces by re-invoking the bench. Each
    # call materializes its own input file copy + output path + task_str
    # — bench-specific details stay in the bench class.
    rollout_seeds = []
    for k in range(K):
        rollout_workdir = workdir / f"r{k}"
        rollout_workdir.mkdir(parents=True, exist_ok=True)
        rs = bench.prepare_seed_data(dataset, idx, rollout_workdir)
        rs["_rollout_idx"] = k
        rs["_diversity"] = diversity
        rs["_diversity_kwargs"] = diversity_kwargs or {}
        rollout_seeds.append(rs)

    # Run K rollouts in parallel under the semaphore.
    # Temperature defaults to 1.0 here (group rollouts) to widen the
    # within-task contrastive split. The regression-gate's K=1 evals
    # keep the provider default for stability.
    exec_results = await asyncio.gather(*[
        run_execute(
            rs, semaphore, skills_dir, model, project_root,
            max_turns, k, cost_tracker, openai_client,
            skill_name=bench.skill_name,
            temperature=1.0,
        )
        for k, rs in enumerate(rollout_seeds)
    ])

    # Assess each rollout. bench.assess may be sync (e.g. SpreadsheetBench
    # invokes soffice which is blocking) — run on threads to avoid
    # blocking the event loop.
    assessments = await asyncio.gather(*[
        asyncio.to_thread(bench.assess, rs, er, k)
        for k, (rs, er) in enumerate(zip(rollout_seeds, exec_results))
    ])

    for k, a in enumerate(assessments):
        a["_rollout_idx"] = k

    return assessments


# ═══════════════════════════════════════════════════════════════════════════
# Classification + advantage helpers (forward-only)
# ═══════════════════════════════════════════════════════════════════════════

def classify_group(group_assessments: list[dict]) -> str:
    """Classify a group by success count.

    Returns one of:
      - ``"all_success"``: every rollout passed (binary is_correct)
      - ``"all_fail"``:    no rollout passed
      - ``"mixed"``:       at least one pass and one fail

    Note: uses the strict binary ``is_correct`` flag. Soft accuracy
    (cell_match% or normalized denotation match%) is available on each
    assessment for downstream group-relative advantage computation.
    """
    n = len(group_assessments)
    n_success = sum(1 for a in group_assessments if a["is_correct"])
    if n_success == n:
        return "all_success"
    if n_success == 0:
        return "all_fail"
    return "mixed"


def group_advantage(
    group_assessments: list[dict],
    reward_key: str = "soft",
) -> list[float]:
    """Compute group-relative advantage per rollout.

    For each rollout k:  ``a_k = r_k - mean(r_*)``
    where r is binary success (``reward_key="hard"``) or soft accuracy
    (``reward_key="soft"``, default).

    Returns a list of K floats, in input order.
    """
    if reward_key == "hard":
        rewards = [1.0 if a["is_correct"] else 0.0 for a in group_assessments]
    elif reward_key == "soft":
        rewards = [a["accuracy"]["accuracy"] for a in group_assessments]
    else:
        raise ValueError(f"reward_key must be 'hard' or 'soft', got {reward_key}")

    if not rewards:
        return []
    mean_r = sum(rewards) / len(rewards)
    return [r - mean_r for r in rewards]


def group_summary(group_assessments: list[dict]) -> dict:
    """One-line summary of a group's outcome distribution.

    Useful for pilot reporting and downstream momentum-record
    annotation.
    """
    K = len(group_assessments)
    n_success = sum(1 for a in group_assessments if a["is_correct"])
    soft_accs = [a["accuracy"]["accuracy"] for a in group_assessments]
    return {
        "K": K,
        "n_success": n_success,
        "n_fail": K - n_success,
        "group_type": classify_group(group_assessments),
        "soft_acc_mean": sum(soft_accs) / K if K else 0.0,
        "soft_acc_min": min(soft_accs) if soft_accs else 0.0,
        "soft_acc_max": max(soft_accs) if soft_accs else 0.0,
        "soft_acc_range": (max(soft_accs) - min(soft_accs)) if soft_accs else 0.0,
        "advantages": group_advantage(group_assessments, reward_key="soft"),
    }
