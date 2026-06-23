"""G2B-Skill training loop — Phase 1+2+3+4 end-to-end.

One iteration:

    GROUP-EXECUTE  (N tasks × K rollouts)
      → CLASSIFY    (per-group: mixed | all_fail | all_success)
      → DIAGNOSE    (3-branch group diagnoser, parallel)
      → ASSEMBLE    (batch_diagnostic_cards.md)
      → MOMENTUM    (group-aware pattern record + overlay; iter≥2 pre-patch
                     + iter==1 bootstrap post-patch, mirroring SkillGrad)
      → PATCH       (4-tier quantitative routing: core/auxiliary/pending/discard)

The optimization analogy:

    parameter         = structured skill package S = (L1, L2, L3, pending_pool)
    loss evidence     = K-rollout outcomes per task + reward distribution
    "gradient"        = per-group diagnostic card with within-task contrast
    momentum          = pattern record M_t + evidence_profile + overlay O_t
    parameter update  = quantitative-routed skill patch
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from bench import Bench, get_bench
from data.layout import (
    base_trajectories_dir_for,
    normalized_dir_for,
    run_dir_for,
    run_id_for,
    splits_dir_for,
)
from data.split import (
    build_fixed_update_training_set,
    build_training_set,
    create_split,
    identify_failures,
    load_split,
)
from pipeline.execution import _write_workspace
from pipeline.group_diagnoser import (
    assemble_group_cards,
    run_group_diagnose,
)
from pipeline.group_execution import (
    classify_group,
    group_summary,
    run_group_execute,
)
from pipeline.group_momentum import run_group_momentum
from pipeline.group_patcher import run_group_patch
from pipeline.regression_gate import (
    evaluate_coreset,
    maybe_rollback,
    maybe_rollback_bilateral,
    select_regression_coreset,
)
from runners.cost_tracker import CostTracker
from runners.model_dispatch import get_client_for_model
from scripts.manifest_update import upsert as manifest_upsert


# ═══════════════════════════════════════════════════════════════════════════
# Skill snapshot (orchestrator-private; kept for forensic inspection)
# ═══════════════════════════════════════════════════════════════════════════

def _snapshot_skill(skills_dir: Path, dest: Path, skill_name: str) -> None:
    skill_dir = skills_dir / skill_name
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / skill_name).exists():
        shutil.rmtree(dest / skill_name)
    shutil.copytree(skill_dir, dest / skill_name)


def _cost_snapshot(ct: CostTracker) -> dict:
    return {
        "input_tokens": ct.input_tokens,
        "cached_tokens": ct.cached_tokens,
        "output_tokens": ct.output_tokens,
        "reasoning_tokens": ct.reasoning_tokens,
        "requests": ct.requests,
        "cost": ct.total_cost,
    }


def _cost_delta(before: dict, after: dict) -> dict:
    return {
        k: round(after[k] - before[k], 6) if isinstance(after[k], float)
           else after[k] - before[k]
        for k in before
    }


# ═══════════════════════════════════════════════════════════════════════════
# Training loop
# ═══════════════════════════════════════════════════════════════════════════

async def run_g2b_training(
    bench: Bench,
    skills_dir: Path,
    model: str,
    project_root: Path,
    output_dir: Path,
    training_config: dict,
    K: int = 4,
    max_turns: int = 30,
    concurrency: int = 4,
    interactive: bool = False,
    start_iteration: int = 1,
    base_trajectories_dir: Path | None = None,
    coreset_size: int = 8,
    coreset_seed: int = 0,
    rollback_epsilon: float = 0.10,
    enable_regression_gate: bool = True,
) -> dict:
    """Run the G2B-Skill training loop.

    Same shape as SkillGrad's ``run_training``, but EVERY task runs K
    rollouts, and the diagnoser/momentum/patcher use the group-aware
    Phase 2/3/4 modules instead of the single-trajectory ones.
    """
    dataset = bench.load_dataset()
    batches = training_config["batches"]
    n_iterations = len(batches)

    cost_tracker = CostTracker(model)
    semaphore = asyncio.Semaphore(concurrency)
    openai_client = get_client_for_model(model)

    id_to_idx = {str(s["id"]): i for i, s in enumerate(dataset)}

    results_path = output_dir / "training_results.json"
    if start_iteration > 1 and results_path.exists():
        results = json.loads(results_path.read_text(encoding="utf-8"))
        print(f"  Loaded {len(results.get('iterations', []))} prior iterations")
    else:
        results = {
            "config": training_config,
            "model": model,
            "skill_name": bench.skill_name,
            "K": K,
            "early_stop": {"all_correct": 4},
            "status": "running",
            "iterations": [],
        }

    output_dir.mkdir(parents=True, exist_ok=True)

    # Pending pool persists across iterations (Phase 4 appends low-strength
    # patterns here; Phase 6 will demote stale entries later).
    pending_pool_path = output_dir / "pending_pool.md"

    # Empty pattern-record placeholder for iter_1's bootstrap momentum call.
    momentum_initial_path = output_dir / "momentum_memory_initial.md"
    if not momentum_initial_path.exists():
        momentum_initial_path.write_text(
            "# Pattern record (initial)\n\n", encoding="utf-8",
        )

    # Phase 6 lite — regression coreset (forward-only acceptance gate)
    coreset_ids: list[str] = []
    if enable_regression_gate and base_trajectories_dir is not None:
        try:
            split_dir = output_dir.parent.parent / "splits"  # not used; pass via arg if needed
            # Use the evolution-pool ids derived from training_config's failure-id-aware
            # build is awkward here; reach back through the config's split.
            # Cleaner: read split.json from results_root.  We accept a coreset_seed
            # and select from base-pass tasks.
            split_path_candidate = (
                output_dir.parent.parent.parent  # results_root
                / "splits"
                / output_dir.parent.parent.name  # likely "runs", but we don't have direct
                # This is brittle; fall back to direct config scan below.
            )
        except Exception:
            pass
        # Try direct read from training_config's seeds + bench name to find split.json
        try:
            _split_path = (
                Path("results") / "splits"
                / f"master_{training_config.get('master_seed', 0)}"
                f"_heldout_{training_config.get('heldout_seed', 42)}"
                / bench.name / "split.json"
            )
            if _split_path.exists():
                _split = json.loads(_split_path.read_text())
                coreset_ids = select_regression_coreset(
                    base_trajectories_dir,
                    _split["evolution_ids"],
                    n_samples=coreset_size,
                    seed=coreset_seed,
                )
                print(f"  Regression coreset: {len(coreset_ids)} base-pass tasks "
                      f"(seed={coreset_seed}): {coreset_ids[:4]}...")
            else:
                print(f"  [warn] split not at {_split_path}; regression gate disabled")
                enable_regression_gate = False
        except Exception as exc:
            print(f"  [warn] coreset select failed: {exc}; regression gate disabled")
            enable_regression_gate = False

    score_before_patch: dict | None = None  # populated each iter from prior scoring

    # Bilateral gate: track base-fail tasks we've successfully passed in
    # training so far. The patch must not regress on these going forward.
    # Sourced from training-pool ids (= base-failures by definition); a
    # task is added once a group on it produces ≥1 success rollout.
    fix_coreset_ids: set[str] = set()

    print(f"\n{'=' * 60}")
    print(f"  G2B-Skill: {n_iterations} iter, "
          f"batch={training_config['batch_size']}, K={K}")
    print(f"  Bench: {bench.name}  Model: {model}  Skills: {skills_dir}")
    if start_iteration > 1:
        print(f"  Resuming from iter {start_iteration}")
    print(f"{'=' * 60}\n")

    consecutive_all_correct = 0
    for prior in results.get("iterations", []):
        if prior.get("result") == "all_correct":
            consecutive_all_correct += 1
        else:
            consecutive_all_correct = 0

    for iter_num in range(start_iteration, n_iterations + 1):
        batch_ids = batches[iter_num - 1]
        iter_dir = output_dir / f"iter_{iter_num}"
        iter_dir.mkdir(parents=True, exist_ok=True)

        t_iter = time.time()
        iter_cost_before = _cost_snapshot(cost_tracker)
        stage_timing: dict = {}
        stage_costs: dict = {}

        print(f"\n{'━' * 60}")
        print(f"  ITER {iter_num}/{n_iterations}  batch: {batch_ids}  K={K}")
        print(f"{'━' * 60}")

        _write_workspace(iter_dir / "batch_seeds.json", batch_ids)

        # Pre-patch snapshot of the skill (forensics)
        snapshot_dir = output_dir / f"snapshot_iter_{iter_num}"
        _snapshot_skill(skills_dir, snapshot_dir, bench.skill_name)
        skill_md_path = skills_dir / bench.skill_name / "SKILL.md"
        if skill_md_path.exists():
            shutil.copy2(skill_md_path,
                         output_dir / f"SKILL.md.iter_{iter_num - 1}")

        # ── GROUP-EXECUTE: K rollouts per task, in parallel groups ──
        print(f"\n  ── GROUP-EXECUTE (N={len(batch_ids)} × K={K}) ──")
        t_stage = time.time()
        cost_before_stage = _cost_snapshot(cost_tracker)

        # Each group's K rollouts share the semaphore; running multiple
        # groups in parallel lets the executor saturate concurrency.
        async def _one_group(task_id: str, idx_pos: int) -> tuple[str, list[dict]]:
            ds_idx = id_to_idx[task_id]
            group_workdir = iter_dir / f"group_{task_id}"
            group_workdir.mkdir(parents=True, exist_ok=True)
            assessments = await run_group_execute(
                bench, dataset, ds_idx, K,
                workdir=group_workdir,
                semaphore=semaphore,
                skills_dir=skills_dir,
                model=model,
                project_root=project_root,
                max_turns=max_turns,
                cost_tracker=cost_tracker,
                openai_client=openai_client,
            )
            return task_id, assessments

        group_results = await asyncio.gather(*[
            _one_group(tid, i) for i, tid in enumerate(batch_ids)
        ])

        # ── CLASSIFY ──
        groups: list[dict] = []
        for task_id, assessments in group_results:
            gtype = classify_group(assessments)
            gsum = group_summary(assessments)
            gsum["task_id"] = task_id
            groups.append({
                "task_id": task_id,
                "assessments": assessments,
                "group_type": gtype,
                "summary": gsum,
            })

        type_counts = {
            "mixed": sum(1 for g in groups if g["group_type"] == "mixed"),
            "all_fail": sum(1 for g in groups if g["group_type"] == "all_fail"),
            "all_success": sum(1 for g in groups if g["group_type"] == "all_success"),
        }
        n_pass = sum(1 for g in groups if g["group_type"] == "all_success")
        n_total = len(groups)
        print(f"\n  ── CLASSIFY: mixed={type_counts['mixed']} "
              f"all_fail={type_counts['all_fail']} "
              f"all_success={type_counts['all_success']} "
              f"(all_success groups = full pass: {n_pass}/{n_total}) ──")
        _write_workspace(iter_dir / "group_classifications.json", [
            {"task_id": g["task_id"], "group_type": g["group_type"],
             "summary": g["summary"]}
            for g in groups
        ])

        # Update fix_coreset: any group with ≥1 success means we've shown
        # the (current) skill can solve this base-fail task. Future patches
        # shouldn't break it.
        for g in groups:
            if g["summary"]["n_success"] >= 1:
                fix_coreset_ids.add(g["task_id"])

        stage_timing["execute_classify"] = round(time.time() - t_stage, 2)
        stage_costs["execute_classify"] = _cost_delta(
            cost_before_stage, _cost_snapshot(cost_tracker)
        )

        # Early-stop: every group all_success
        if type_counts["all_success"] == n_total:
            consecutive_all_correct += 1
            print(f"  All groups all_success (streak: {consecutive_all_correct})")
            results["iterations"].append({
                "iteration": iter_num,
                "batch": batch_ids,
                "result": "all_correct",
                "type_counts": type_counts,
                "duration_s": round(time.time() - t_iter, 2),
                "cost": _cost_delta(iter_cost_before,
                                    _cost_snapshot(cost_tracker)),
                "stage_timing": stage_timing,
                "stage_costs": stage_costs,
            })
            _write_workspace(output_dir / "training_results.json", results)
            if consecutive_all_correct >= 4:
                print("\n  EARLY STOP: 4 consecutive all_correct iters")
                break
            continue

        consecutive_all_correct = 0

        # ── DIAGNOSE (3-branch, parallel per group) ──
        print(f"\n  ── DIAGNOSE ──")
        t_stage = time.time()
        cost_before_stage = _cost_snapshot(cost_tracker)

        async def _diag_one(g: dict) -> dict:
            return await run_group_diagnose(
                g["assessments"],
                g["group_type"],
                task_str=g["assessments"][0]["task_str"],
                iter_id=str(iter_num),
                iter_dir=iter_dir,
                skills_dir=skills_dir,
                skill_name=bench.skill_name,
                model=model,
                project_root=project_root,
                semaphore=semaphore,
                cost_tracker=cost_tracker,
            )

        diagnoses = await asyncio.gather(*[_diag_one(g) for g in groups])

        cards_path = iter_dir / "batch_diagnostic_cards.md"
        assemble_group_cards(diagnoses, cards_path)

        stage_timing["diagnose"] = round(time.time() - t_stage, 2)
        stage_costs["diagnose"] = _cost_delta(
            cost_before_stage, _cost_snapshot(cost_tracker)
        )

        # ── MOMENTUM ──
        record_path = iter_dir / "momentum_memory.md"
        overlay_path = iter_dir / "momentum_overlay.md"
        if iter_num >= 2:
            print(f"\n  ── MOMENTUM ──")
            t_stage = time.time()
            cost_before_stage = _cost_snapshot(cost_tracker)
            previous_record = output_dir / f"iter_{iter_num - 1}" / "momentum_memory.md"
            if not previous_record.exists():
                previous_record = momentum_initial_path
            await run_group_momentum(
                cards_path=cards_path,
                previous_record_path=previous_record,
                skills_dir=skills_dir,
                skill_name=bench.skill_name,
                record_output_path=record_path,
                overlay_output_path=overlay_path,
                model=model,
                project_root=project_root,
                cost_tracker=cost_tracker,
                iter_dir=iter_dir,
                iter_num=iter_num,
            )
            stage_timing["momentum"] = round(time.time() - t_stage, 2)
            stage_costs["momentum"] = _cost_delta(
                cost_before_stage, _cost_snapshot(cost_tracker)
            )
        else:
            # iter_1 bootstrap (pre-patch so the patcher has a populated record)
            print(f"\n  ── MOMENTUM bootstrap (iter_1) ──")
            t_stage = time.time()
            cost_before_stage = _cost_snapshot(cost_tracker)
            await run_group_momentum(
                cards_path=cards_path,
                previous_record_path=momentum_initial_path,
                skills_dir=skills_dir,
                skill_name=bench.skill_name,
                record_output_path=record_path,
                overlay_output_path=overlay_path,
                model=model,
                project_root=project_root,
                cost_tracker=cost_tracker,
                iter_dir=iter_dir,
                iter_num=iter_num,
            )
            stage_timing["momentum_bootstrap"] = round(time.time() - t_stage, 2)
            stage_costs["momentum_bootstrap"] = _cost_delta(
                cost_before_stage, _cost_snapshot(cost_tracker)
            )

        # ── PATCH ──
        print(f"\n  ── PATCH ──")
        t_stage = time.time()
        cost_before_stage = _cost_snapshot(cost_tracker)

        # Anti-wipe nuclear backstop (ported from v8_training.py 2026-06-19):
        # Capture pre-patch SKILL.md so we can revert if the patcher
        # wholesale-rewrites a developed skill (>50% size drop). Without
        # this, GPT-4.1 weak backbone periodically wipes accumulated
        # content; v8_training paper-grade results depend on this guard.
        skill_md_path = skills_dir / bench.skill_name / "SKILL.md"
        pre_patch_size = skill_md_path.stat().st_size if skill_md_path.exists() else 0
        pre_patch_text = (
            skill_md_path.read_text(encoding="utf-8")
            if skill_md_path.exists() else ""
        )

        patch_result = await run_group_patch(
            cards_path=cards_path,
            overlay_path=overlay_path,
            record_path=record_path,
            pending_pool_path=pending_pool_path,
            skills_dir=skills_dir,
            skill_name=bench.skill_name,
            model=model,
            project_root=project_root,
            cost_tracker=cost_tracker,
            iter_dir=iter_dir,
            iter_num=iter_num,
            fix_coreset_ids=sorted(fix_coreset_ids) if fix_coreset_ids else None,
        )

        # Anti-wipe revert: if SKILL.md shrank > 50% (and pre-patch was
        # substantive, > 1500 bytes ≈ 50 lines), revert.
        # Anti-wipe revert #2: front-matter check. If the patcher produced
        # SKILL.md whose first 4 bytes are not ``---\n`` (YAML frontmatter
        # marker), the Claude runtime can no longer register the skill via
        # `name:` and every subsequent executor call returns "skill not
        # found" — silent training-time damage. Detect missing frontmatter
        # and revert to pre-patch state. Triggers regardless of size delta.
        anti_wipe_triggered = False
        if skill_md_path.exists() and pre_patch_size > 1500:
            post_patch_size = skill_md_path.stat().st_size
            if post_patch_size < pre_patch_size * 0.5:
                print(
                    f"  [PATCH-GUARD] WIPE detected: {pre_patch_size}B → "
                    f"{post_patch_size}B "
                    f"({100*(post_patch_size-pre_patch_size)/pre_patch_size:.0f}%). "
                    f"REVERTING."
                )
                skill_md_path.write_text(pre_patch_text, encoding="utf-8")
                anti_wipe_triggered = True
        # Frontmatter check (size-independent)
        if (
            not anti_wipe_triggered
            and skill_md_path.exists()
            and pre_patch_text.startswith("---")
        ):
            post_text = skill_md_path.read_text(encoding="utf-8")
            if not post_text.startswith("---"):
                print(
                    f"  [PATCH-GUARD] FRONTMATTER lost (post-patch first "
                    f"chars: {post_text[:40]!r}). Pre-patch had valid "
                    f"frontmatter. REVERTING to preserve skill registration."
                )
                skill_md_path.write_text(pre_patch_text, encoding="utf-8")
                anti_wipe_triggered = True

        stage_timing["patch"] = round(time.time() - t_stage, 2)
        stage_costs["patch"] = _cost_delta(
            cost_before_stage, _cost_snapshot(cost_tracker)
        )
        if anti_wipe_triggered:
            stage_costs.setdefault("patch_guard", {})["wipe_reverted"] = True

        # ── REGRESSION GATE (Phase 6 lite, bilateral) ──
        gate_result: dict | None = None
        if enable_regression_gate and coreset_ids:
            t_stage = time.time()
            cost_before_stage = _cost_snapshot(cost_tracker)
            # Sample up to N from fix_coreset_ids so we don't blow cost.
            import random as _random
            fix_ids_list = sorted(fix_coreset_ids)
            if len(fix_ids_list) > coreset_size:
                fix_ids_list = _random.Random(coreset_seed + iter_num).sample(
                    fix_ids_list, coreset_size
                )
            print(f"\n  ── REGRESSION-GATE  (pass={len(coreset_ids)} fix={len(fix_ids_list)}) ──")
            gate_workdir = iter_dir / "regression_gate"

            # Score base-pass coreset (don't break what already worked)
            score_before_pass = await evaluate_coreset(
                bench, dataset, coreset_ids,
                skills_dir=snapshot_dir,
                skill_name=bench.skill_name,
                workdir=gate_workdir / "before_pass",
                semaphore=semaphore,
                model=model, project_root=project_root,
                cost_tracker=cost_tracker, openai_client=openai_client,
                max_turns=max_turns,
            )
            score_after_pass = await evaluate_coreset(
                bench, dataset, coreset_ids,
                skills_dir=skills_dir,
                skill_name=bench.skill_name,
                workdir=gate_workdir / "after_pass",
                semaphore=semaphore,
                model=model, project_root=project_root,
                cost_tracker=cost_tracker, openai_client=openai_client,
                max_turns=max_turns,
            )

            # Score fix coreset (don't lose what we just learned to fix)
            if fix_ids_list:
                score_before_fix = await evaluate_coreset(
                    bench, dataset, fix_ids_list,
                    skills_dir=snapshot_dir,
                    skill_name=bench.skill_name,
                    workdir=gate_workdir / "before_fix",
                    semaphore=semaphore,
                    model=model, project_root=project_root,
                    cost_tracker=cost_tracker, openai_client=openai_client,
                    max_turns=max_turns,
                )
                score_after_fix = await evaluate_coreset(
                    bench, dataset, fix_ids_list,
                    skills_dir=skills_dir,
                    skill_name=bench.skill_name,
                    workdir=gate_workdir / "after_fix",
                    semaphore=semaphore,
                    model=model, project_root=project_root,
                    cost_tracker=cost_tracker, openai_client=openai_client,
                    max_turns=max_turns,
                )
                gate_result = maybe_rollback_bilateral(
                    pre_patch_snapshot=snapshot_dir,
                    skills_dir=skills_dir, skill_name=bench.skill_name,
                    score_before_pass=score_before_pass,
                    score_after_pass=score_after_pass,
                    score_before_fix=score_before_fix,
                    score_after_fix=score_after_fix,
                    epsilon=rollback_epsilon,
                )
            else:
                # First iter or no fixes yet — fall back to single-coreset.
                gate_result = maybe_rollback(
                    pre_patch_snapshot=snapshot_dir,
                    skills_dir=skills_dir, skill_name=bench.skill_name,
                    score_before=score_before_pass,
                    score_after=score_after_pass,
                    epsilon=rollback_epsilon,
                    extra_label="pass-only (no fix coreset yet)",
                )

            stage_timing["regression_gate"] = round(time.time() - t_stage, 2)
            stage_costs["regression_gate"] = _cost_delta(
                cost_before_stage, _cost_snapshot(cost_tracker)
            )
            print(f"  ── GATE: decision={gate_result['decision']}")
            if "pass_coreset" in gate_result:
                pc = gate_result["pass_coreset"]; fc = gate_result["fix_coreset"]
                print(f"          pass {pc['before']['hard']:.1%}->{pc['after']['hard']:.1%} (Δ={pc['delta_hard']:+.3f})")
                print(f"          fix  {fc['before']['hard']:.1%}->{fc['after']['hard']:.1%} (Δ={fc['delta_hard']:+.3f})")
            else:
                print(f"          {gate_result.get('label','')} Δ={gate_result.get('delta_hard',0):+.3f}")
            _write_workspace(iter_dir / "regression_gate.json", gate_result)

        pre_pass = sum(
            1 for g in groups for a in g["assessments"] if a["is_correct"]
        )
        n_rollouts = sum(len(g["assessments"]) for g in groups)
        pre_soft = (
            sum(a["accuracy"]["accuracy"] for g in groups for a in g["assessments"])
            / max(n_rollouts, 1)
        )
        routes = [r["route"] for r in patch_result.get("routing_summary", [])]
        print(f"\n  ── PATCHED  pre_pass={pre_pass}/{n_rollouts}  "
              f"soft={pre_soft:.1%}  routes={routes}")

        iter_duration = round(time.time() - t_iter, 2)
        iter_cost = _cost_delta(iter_cost_before, _cost_snapshot(cost_tracker))
        results["iterations"].append({
            "iteration": iter_num,
            "batch": batch_ids,
            "result": "patched",
            "type_counts": type_counts,
            "pre_pass": pre_pass,
            "n_rollouts": n_rollouts,
            "pre_soft_accuracy": round(pre_soft, 4),
            "group_summaries": [g["summary"] for g in groups],
            "diagnosis_branches": [d["branch"] for d in diagnoses],
            "schema_violations": sum(
                len(d.get("violations", [])) for d in diagnoses
            ),
            "routing_summary": patch_result.get("routing_summary", []),
            "regression_gate": gate_result,
            "duration_s": iter_duration,
            "cost": iter_cost,
            "stage_timing": stage_timing,
            "stage_costs": stage_costs,
        })
        results["cumulative_cost"] = _cost_snapshot(cost_tracker)
        _write_workspace(output_dir / "training_results.json", results)

        if interactive:
            try:
                user_input = input(
                    "\n  Enter to continue, or 'stop' to halt: "
                ).strip().lower()
                if user_input == "stop":
                    break
            except EOFError:
                break

    results["status"] = "completed"
    results["cost"] = cost_tracker.to_dict()
    _write_workspace(output_dir / "training_results.json", results)

    final_dir = output_dir / "final_skill" / bench.skill_name
    final_dir.mkdir(parents=True, exist_ok=True)
    src = skills_dir / bench.skill_name
    if src.exists():
        if final_dir.exists():
            shutil.rmtree(final_dir)
        shutil.copytree(src, final_dir)

    print(f"\n{'=' * 60}")
    print(f"  G2B-Skill training complete")
    print(f"  Final skill: {final_dir}")
    print(f"  Cost:\n{cost_tracker.summary()}")
    print(f"{'=' * 60}")
    return results


# ═══════════════════════════════════════════════════════════════════════════
# CLI entrypoint
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="G2B-Skill training loop: group-execute -> diagnose "
                    "-> momentum -> patch (Phase 1+2+3+4)."
    )
    parser.add_argument("--bench", choices=["spreadsheet", "wtq", "officeqa"],
                        default="spreadsheet")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--skills-dir", default="seeds")
    parser.add_argument("--results-root", default="results")
    parser.add_argument("--base-trajectories-dir", default=None)
    parser.add_argument("--method", default="g2b-skill")
    parser.add_argument("--model", default="gpt-5.4")
    parser.add_argument("--config-tag", default=None)
    parser.add_argument("--master-seed", type=int, default=0)
    parser.add_argument("--heldout-seed", type=int, default=42)
    parser.add_argument("--training-seed", type=int, default=0)
    parser.add_argument("--n-train", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--K", type=int, default=4,
                        help="Rollouts per task per iteration (group size).")
    parser.add_argument("--batch-schedule",
                        choices=["epoch", "fixed-updates"], default="epoch")
    parser.add_argument("--n-iterations", type=int, default=None)
    parser.add_argument("--batch-seed", type=int, default=None)
    parser.add_argument("--max-turns", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--start-iteration", type=int, default=1)
    parser.add_argument("--coreset-size", type=int, default=8,
                        help="Phase 6 lite — # base-pass tasks in regression coreset.")
    parser.add_argument("--rollback-epsilon", type=float, default=0.10,
                        help="Phase 6 lite — rollback if hard-acc Δ < -ε on coreset.")
    parser.add_argument("--no-regression-gate", action="store_true",
                        help="Disable Phase 6 regression-gate (ablation).")
    args = parser.parse_args()

    results_root = Path(args.results_root)
    if args.data_dir:
        data_dir = Path(args.data_dir)
    elif args.bench == "spreadsheet":
        data_dir = normalized_dir_for(results_root)
    elif args.bench == "wtq":
        data_dir = Path("data/benchmarks/wikitablequestions")
    elif args.bench == "officeqa":
        data_dir = Path("data/benchmarks/officeqa")
    else:
        raise ValueError(f"unknown bench {args.bench!r}")
    bench = get_bench(args.bench, data_dir=str(data_dir))

    split_dir = splits_dir_for(results_root, args.master_seed,
                               args.heldout_seed, args.bench)
    base_traj_dir = base_trajectories_dir_for(
        results_root, args.master_seed, args.heldout_seed,
        args.model, args.bench,
    )
    if args.base_trajectories_dir:
        base_traj_dir = Path(args.base_trajectories_dir).resolve()

    split_path = split_dir / "split.json"
    if not split_path.exists():
        print(f"Creating split at {split_dir}...")
        normalized_dir = normalized_dir_for(results_root)
        create_split(
            bench, split_dir,
            master_seed=args.master_seed,
            heldout_seed=args.heldout_seed,
            normalized_dir=normalized_dir,
        )
    split = load_split(split_dir)
    print(f"Split: {split['n_evolution']} evolution, {split['n_test']} test")

    failures_path = base_traj_dir / "failure_ids.json"
    if not failures_path.exists():
        # Fall back to bench-level (sibling) location
        sibling = base_traj_dir.parent / "failure_ids.json"
        if sibling.exists():
            failures_path = sibling
    if not failures_path.exists():
        raise FileNotFoundError(
            f"No failure_ids.json at {failures_path}. Run base_traj first "
            f"(scripts/base_traj.sh BENCH={args.bench})."
        )
    failure_ids = json.loads(failures_path.read_text(encoding="utf-8"))["failure_ids"]
    print(f"Loaded {len(failure_ids)} failure IDs from {failures_path}")

    if args.batch_schedule == "fixed-updates":
        if args.n_iterations is None:
            parser.error("--n-iterations required for fixed-updates")
        training_config = build_fixed_update_training_set(
            failure_ids=failure_ids,
            training_seed=args.training_seed,
            n_train=args.n_train,
            batch_size=args.batch_size,
            n_iterations=args.n_iterations,
            batch_seed=args.batch_seed,
        )
    else:
        if args.n_iterations is not None:
            parser.error("--n-iterations requires fixed-updates")
        training_config = build_training_set(
            failure_ids, args.training_seed, args.n_train, args.batch_size,
        )
    training_config.update({
        "model": args.model, "max_turns": args.max_turns,
        "concurrency": args.concurrency, "K": args.K,
        "bench": args.bench,
        "master_seed": args.master_seed, "heldout_seed": args.heldout_seed,
    })

    # Bench-keyed run_id so SS and WTQ runs don't collide on disk.
    method_with_bench = f"{args.method}-{args.bench}"
    run_id = run_id_for(method=method_with_bench, model=args.model,
                        config_tag=args.config_tag)
    run_dir = run_dir_for(results_root, run_id)
    train_dir = run_dir / "train"
    train_dir.mkdir(parents=True, exist_ok=True)
    _write_workspace(train_dir / "train_set.json", training_config)
    print(f"Run id: {run_id}\nRun dir: {run_dir}")

    started_at = datetime.now(timezone.utc).isoformat()
    config_payload = {
        "run_id": run_id,
        "method": args.method,
        "bench": args.bench,
        "model": args.model,
        "config_tag": args.config_tag,
        "seeds": {
            "master_seed": args.master_seed,
            "heldout_seed": args.heldout_seed,
            "training_seed": args.training_seed,
        },
        "split_path": str(split_path),
        "base_trajectories_path": str(base_traj_dir),
        "training_config": {
            "n_train": args.n_train,
            "batch_size": args.batch_size,
            "K": args.K,
            "batch_schedule": args.batch_schedule,
            "n_iterations": args.n_iterations,
            "batch_seed": args.batch_seed,
            "max_turns": args.max_turns,
            "concurrency": args.concurrency,
        },
        "started": started_at,
        "status": "running",
    }
    _write_workspace(run_dir / "config.json", config_payload)
    manifest_upsert(results_root, run_dir)

    skills_work_dir = run_dir / "skills"
    if not (skills_work_dir / bench.skill_name / "SKILL.md").exists():
        base_skill_dir = Path(args.skills_dir)
        skill_dest = skills_work_dir / bench.skill_name
        skill_dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base_skill_dir / bench.skill_name / "SKILL.md",
                     skill_dest / "SKILL.md")
        refs_src = base_skill_dir / bench.skill_name / "references"
        if refs_src.exists():
            shutil.copytree(refs_src, skill_dest / "references")
        print(f"Copied base skill to {skills_work_dir}")

    t_start = time.time()
    try:
        results = asyncio.run(run_g2b_training(
            bench=bench,
            skills_dir=skills_work_dir,
            model=args.model,
            project_root=Path(".").resolve(),
            output_dir=train_dir,
            training_config=training_config,
            K=args.K,
            max_turns=args.max_turns,
            concurrency=args.concurrency,
            interactive=args.interactive,
            start_iteration=args.start_iteration,
            base_trajectories_dir=base_traj_dir,
            coreset_size=args.coreset_size,
            coreset_seed=args.training_seed,
            rollback_epsilon=args.rollback_epsilon,
            enable_regression_gate=not args.no_regression_gate,
        ))
        final_status = "completed"
    except Exception as exc:
        results = None
        final_status = f"failed: {exc}"
        raise
    finally:
        cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
        cfg["status"] = final_status
        cfg["completed"] = datetime.now(timezone.utc).isoformat()
        cfg["elapsed_s"] = round(time.time() - t_start, 1)
        if results is not None:
            iters = results.get("iterations", [])
            cfg["metrics"] = {
                "n_iterations": len(iters),
                "n_patched": sum(1 for i in iters if i.get("result") == "patched"),
                "n_all_correct": sum(1 for i in iters if i.get("result") == "all_correct"),
                "test_hard": None, "test_cell_acc": None,
            }
            cfg["cost"] = results.get("cost") or results.get("cumulative_cost")
        _write_workspace(run_dir / "config.json", cfg)
        manifest_upsert(results_root, run_dir)

    print(f"\nResults: {train_dir / 'training_results.json'}")
    print(f"Skill:   {train_dir / 'final_skill' / bench.skill_name / 'SKILL.md'}")
    print(f"Config:  {run_dir / 'config.json'}")


if __name__ == "__main__":
    main()
