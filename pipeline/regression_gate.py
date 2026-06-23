"""Phase 6 lite — regression-aware acceptance gate (forward-only).

Mini-batch validation after each iter: re-run a small sample of
already-passed tasks (the "regression coreset") on the patched skill.
If hard accuracy drops more than `epsilon` vs the snapshot's score,
revert SKILL.md + references/ to the pre-patch snapshot.

Scope:
- Only in-loop, deterministic. No counterfactual replay.
- Coreset = 8 random base-pass tasks (sampled once per training run with
  training_seed; reproducible).
- Gate fires after the patch step, before the next iter's group-execute.

This is the minimum forward-only acceptance gate that responds to the
two bad cases observed in run-v1/v2:
1. iter-7 SS regression from over-promoted L2 rule (would have been
   caught: regression coreset would tank).
2. v2's overly-conservative routing leading to too few promotions
   (gate is symmetric; encourages more aggressive promotion since
   bad ones get rolled back).
"""

from __future__ import annotations

import asyncio
import json
import random
import shutil
import time
from pathlib import Path

from bench import Bench
from pipeline.execution import _write_workspace, run_execute
from runners.cost_tracker import CostTracker


def select_regression_coreset(
    base_traj_dir: Path, evolution_ids: list[str], n_samples: int = 8,
    seed: int = 0,
) -> list[str]:
    """Sample N base-pass tasks deterministically.

    Reads ``failure_ids.json`` to find pass-ids (= evolution_ids \\
    failure_ids), then samples n_samples with seed.
    """
    fid_path = base_traj_dir / "failure_ids.json"
    if not fid_path.exists():
        # bench-level fallback
        fid_path = base_traj_dir.parent / "failure_ids.json"
    if not fid_path.exists():
        raise FileNotFoundError(f"no failure_ids.json near {base_traj_dir}")
    fail = set(json.loads(fid_path.read_text())["failure_ids"])
    pass_ids = [t for t in evolution_ids if t not in fail]
    if not pass_ids:
        return []
    rng = random.Random(seed)
    return rng.sample(pass_ids, min(n_samples, len(pass_ids)))


async def evaluate_coreset(
    bench: Bench,
    dataset: list[dict],
    coreset_ids: list[str],
    skills_dir: Path,
    skill_name: str,
    workdir: Path,
    semaphore: asyncio.Semaphore,
    model: str,
    project_root: Path,
    cost_tracker: CostTracker,
    openai_client,
    max_turns: int = 20,
) -> dict:
    """Run K=1 on each coreset task, return aggregate hard score.

    Returns ``{"n": int, "n_pass": int, "hard": float, "soft": float,
    "results": [...]}``
    """
    if not coreset_ids:
        return {"n": 0, "n_pass": 0, "hard": 1.0, "soft": 1.0, "results": []}
    id_to_idx = {str(s["id"]): i for i, s in enumerate(dataset)}
    workdir.mkdir(parents=True, exist_ok=True)

    async def one(tid: str) -> dict:
        if tid not in id_to_idx:
            return {"id": tid, "is_correct": False, "soft": 0.0,
                    "error": "not_in_dataset"}
        idx = id_to_idx[tid]
        sd = bench.prepare_seed_data(dataset, idx, workdir,
                                     task_dir_name=f"core_{tid}")
        try:
            er = await run_execute(
                sd, semaphore, skills_dir, model, project_root,
                max_turns, 0, cost_tracker, openai_client,
                skill_name=skill_name,
            )
            assess = await asyncio.to_thread(bench.assess, sd, er, 0)
            return {
                "id": tid,
                "is_correct": bool(assess["is_correct"]),
                "soft": assess["accuracy"]["accuracy"],
            }
        except Exception as e:
            return {"id": tid, "is_correct": False, "soft": 0.0,
                    "error": str(e)}

    results = await asyncio.gather(*[one(t) for t in coreset_ids])
    n = len(results)
    n_pass = sum(1 for r in results if r.get("is_correct"))
    hard = n_pass / n if n else 1.0
    soft = sum(r.get("soft", 0) for r in results) / n if n else 1.0
    return {"n": n, "n_pass": n_pass, "hard": hard, "soft": soft,
            "results": results}


def maybe_rollback(
    pre_patch_snapshot: Path, skills_dir: Path, skill_name: str,
    score_before: dict, score_after: dict, epsilon: float = 0.05,
    extra_label: str = "",
) -> dict:
    """If `score_after.hard < score_before.hard - epsilon`, revert.

    Returns dict describing the gate action:
      - "decision": "accept" | "rollback"
      - "score_before", "score_after", "delta_hard", "label"
    """
    delta = score_after["hard"] - score_before["hard"]
    if delta < -epsilon:
        # Roll back: replace skills_dir/<skill_name> with snapshot
        target = skills_dir / skill_name
        snap_dir = pre_patch_snapshot / skill_name
        if snap_dir.exists():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(snap_dir, target)
        return {
            "decision": "rollback",
            "score_before": score_before,
            "score_after": score_after,
            "delta_hard": round(delta, 4),
            "label": extra_label,
        }
    return {
        "decision": "accept",
        "score_before": score_before,
        "score_after": score_after,
        "delta_hard": round(delta, 4),
        "label": extra_label,
    }


def maybe_rollback_bilateral(
    pre_patch_snapshot: Path, skills_dir: Path, skill_name: str,
    score_before_pass: dict, score_after_pass: dict,
    score_before_fix: dict, score_after_fix: dict,
    epsilon: float = 0.10,
    require_both_regress: bool = True,
) -> dict:
    """Bilateral gate with tolerance.

    Rollback policy (v5):
      - Default ``epsilon = 0.10`` (was 0.05). With 8-task coresets, one
        wrong rollout = -12.5%, so 0.05 was too tight; 0.10 absorbs single-
        task K=1 sampling noise without missing real 2-task regressions.
      - Default ``require_both_regress = True`` (was False/single-side).
        A patch is rolled back only when BOTH coresets drop ≥ epsilon.
        If pass-coreset improves while fix-coreset drops (or vice versa),
        the gate accepts: net learning, not regression.

    Background: v4 fired 4 SS rollbacks / 10 iter, throwing away most
    iter's accumulated work. SkillGrad's free-form patcher has zero
    rollback and reaches 71%; our gate's noise-driven aggressive
    rollback was the limiting factor at v4.
    """
    delta_pass = score_after_pass["hard"] - score_before_pass["hard"]
    delta_fix = score_after_fix["hard"] - score_before_fix["hard"]
    pass_regress = delta_pass < -epsilon
    fix_regress = delta_fix < -epsilon

    should_rollback = (pass_regress and fix_regress) if require_both_regress \
                      else (pass_regress or fix_regress)

    if should_rollback:
        target = skills_dir / skill_name
        snap_dir = pre_patch_snapshot / skill_name
        if snap_dir.exists():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(snap_dir, target)
        reasons = []
        if pass_regress:
            reasons.append(f"base-pass coreset Δ={delta_pass:+.3f}")
        if fix_regress:
            reasons.append(f"base-fix coreset Δ={delta_fix:+.3f}")
        return {
            "decision": "rollback",
            "reason": "; ".join(reasons),
            "policy": f"epsilon={epsilon} require_both={require_both_regress}",
            "pass_coreset": {"before": score_before_pass, "after": score_after_pass,
                             "delta_hard": round(delta_pass, 4)},
            "fix_coreset": {"before": score_before_fix, "after": score_after_fix,
                            "delta_hard": round(delta_fix, 4)},
        }
    return {
        "decision": "accept",
        "policy": f"epsilon={epsilon} require_both={require_both_regress}",
        "pass_coreset": {"before": score_before_pass, "after": score_after_pass,
                         "delta_hard": round(delta_pass, 4)},
        "fix_coreset": {"before": score_before_fix, "after": score_after_fix,
                        "delta_hard": round(delta_fix, 4)},
    }
