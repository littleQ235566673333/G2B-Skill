"""v8 training loop = v7 + group-state-aware diagnose dispatch.

Differences vs pipeline/v7_training.py:
  - DIAGNOSE step dispatches per task by group_type:
      mixed       -> run_mixed_group_k_trace_diagnose (K traces in one call)
      all_fail    -> run_all_fail_cluster_diagnose    (K traces in one call)
      all_success -> run_diagnose(type="contrastive") (cross-version vs base)
  - classify_batch (which split by primary's is_correct) is replaced with
    explicit group_type dispatch.
  - Trajectory utilization rises from ~25% (v7) to ~62% (v8) of K*batch.

Everything else (group EXECUTE, group_evidence injection into PATCH, momentum,
final skill snapshot) is identical to v7.
"""

from __future__ import annotations
import asyncio, json, shutil, time
from pathlib import Path

from bench import Bench
from pipeline.diagnoser import assemble_diagnoses, run_diagnose
from pipeline.execution import _write_workspace
from pipeline.group_execution import run_group_execute
from pipeline.momentum import run_momentum
from pipeline.patcher import run_patch
from pipeline.training import _log_iteration, _write_iter_summary, _snapshot_skill
from pipeline.v7_helpers import build_group_evidence_md, pick_primary_assessment
from pipeline.v8_diagnoser import (
    run_all_fail_cluster_diagnose,
    run_mixed_group_k_trace_diagnose,
)
from runners.cost_tracker import CostTracker
from runners.model_dispatch import get_client_for_model


def _cost_snapshot(ct: CostTracker) -> dict:
    return {"input_tokens": ct.input_tokens, "cached_tokens": ct.cached_tokens,
            "output_tokens": ct.output_tokens, "reasoning_tokens": ct.reasoning_tokens,
            "requests": ct.requests, "cost": ct.total_cost}


def _cost_delta(before: dict, after: dict) -> dict:
    return {k: round(after[k] - before[k], 6) if isinstance(after[k], float) else after[k] - before[k]
            for k in before}


def _classify_group(group: list[dict]) -> str:
    K = len(group)
    n_succ = sum(1 for a in group if a["is_correct"])
    if n_succ == K: return "all_success"
    if n_succ == 0: return "all_fail"
    return "mixed"


def _assign_evidence_tiers(diagnoses: list[dict], group_types: dict[str, str]) -> dict[str, str]:
    """Tag each diagnosis with evidence_id (E1, E2, ...) and tier; return
    dict mapping evidence_id -> tier.

    Tier rules:
      - mixed group → "high"  (within-group contrastive)
      - all_fail CONVERGENT → "medium", DIVERGENT → "low"
      - all_success / contrastive vs base → "protect" (don't disturb working sections)
    """
    import re as _re
    tiers: dict[str, str] = {}
    for idx, d in enumerate(diagnoses):
        eid = f"E{idx+1}"
        d["evidence_id"] = eid
        gtype = group_types.get(d["id"], "unknown")
        if gtype == "mixed":
            tier = "high"
        elif gtype == "all_fail":
            text = d.get("diagnosis", "").upper()
            if _re.search(r"\bCONVERGENT\b", text):
                tier = "medium"
            elif _re.search(r"\bDIVERGENT\b", text):
                tier = "low"
            else:
                tier = "low"
        else:  # all_success → contrastive vs base
            tier = "protect"
        d["tier"] = tier
        tiers[eid] = tier
    return tiers


def _assemble_v8_diagnoses(
    diagnoses: list[dict], assessments: list[dict], output_path,
):
    """Like assemble_diagnoses but prepends [Evidence E_X, tier=...] tags to
    each task header so the patcher can cite them in its mapping."""
    from pathlib import Path
    acc_by_id = {a["id"]: a for a in assessments}
    lines = ["# Batch Diagnoses\n"]
    for diag in diagnoses:
        ex_id = diag["id"]
        eid = diag.get("evidence_id", "E?")
        tier = diag.get("tier", "none")
        dtype = diag.get("type", "")
        assessment = acc_by_id.get(ex_id, {})
        acc = assessment.get("accuracy", {})
        if isinstance(acc, dict):
            acc_v = acc.get("accuracy", 0)
        else:
            acc_v = acc or 0
        header = f"## [Evidence {eid}, tier={tier}] Task {ex_id} ({dtype}, accuracy: {acc_v:.0%})"
        lines.append(f"\n{header}\n")
        lines.append(diag["diagnosis"])
        lines.append("")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return output_path


async def run_v8_training(
    bench: Bench,
    skills_dir: Path,
    model: str,
    project_root: Path,
    output_dir: Path,
    base_trajectories_dir: Path,
    training_config: dict,
    K: int = 4,
    max_turns: int = 30,
    concurrency: int = 4,
    interactive: bool = False,
    start_iteration: int = 1,
):
    """v8 training loop — see module docstring."""
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
    else:
        results = {
            "config": training_config, "model": model, "skill_name": bench.skill_name,
            "K": K, "method": "v8", "early_stop": {"all_correct": 4},
            "status": "running", "iterations": [],
        }

    consecutive_all_correct = 0
    for prior in results.get("iterations", []):
        if prior.get("result") == "all_correct":
            consecutive_all_correct += 1
        else:
            consecutive_all_correct = 0

    output_dir.mkdir(parents=True, exist_ok=True)
    momentum_initial_path = output_dir / "momentum_memory_initial.md"
    if not momentum_initial_path.exists():
        momentum_initial_path.write_text("# Pattern record (initial)\n\n", encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"  v8 training: {n_iterations} iter, K={K}, batch_size={training_config['batch_size']}")
    print(f"  Method: SkillGrad pipes + K-rollout group + group-aware diagnose dispatch")
    print(f"  Model: {model} | Skills: {skills_dir}")
    print(f"{'=' * 60}\n")

    for iter_num in range(start_iteration, n_iterations + 1):
        await _run_iter(
            iter_num=iter_num, batch_ids=batches[iter_num - 1],
            output_dir=output_dir, dataset=dataset, id_to_idx=id_to_idx,
            bench=bench, skills_dir=skills_dir, K=K, max_turns=max_turns,
            semaphore=semaphore, model=model, project_root=project_root,
            cost_tracker=cost_tracker, openai_client=openai_client,
            base_trajectories_dir=base_trajectories_dir,
            momentum_initial_path=momentum_initial_path,
            n_iterations=n_iterations, results=results,
            consecutive_all_correct_ref=[consecutive_all_correct],
        )
        # update streak from results
        last = results["iterations"][-1] if results["iterations"] else {}
        if last.get("result") == "all_correct":
            consecutive_all_correct += 1
        else:
            consecutive_all_correct = 0
        if consecutive_all_correct >= 4:
            print(f"\n  EARLY STOP: 4 consecutive all-correct iterations")
            break
        if interactive:
            try:
                if input("\n  Press Enter / 'stop': ").strip().lower() == "stop": break
            except EOFError: break

    results["status"] = "completed"
    results["cost"] = cost_tracker.to_dict()
    _write_workspace(output_dir / "training_results.json", results)

    final_dir = output_dir / "final_skill" / bench.skill_name
    final_dir.mkdir(parents=True, exist_ok=True)
    skill_xlsx = skills_dir / bench.skill_name
    if skill_xlsx.exists():
        if final_dir.exists(): shutil.rmtree(final_dir)
        shutil.copytree(skill_xlsx, final_dir)
    print(f"\n{'=' * 60}\n  v8 training complete\n  Final: {final_dir}\n{'=' * 60}")
    return results


async def _run_iter(
    iter_num, batch_ids, output_dir, dataset, id_to_idx, bench, skills_dir,
    K, max_turns, semaphore, model, project_root, cost_tracker, openai_client,
    base_trajectories_dir, momentum_initial_path, n_iterations, results,
    consecutive_all_correct_ref,
):
    iter_dir = output_dir / f"iter_{iter_num}"
    iter_dir.mkdir(parents=True, exist_ok=True)
    _snapshot_skill(skills_dir, output_dir / f"snapshot_iter_{iter_num}", bench.skill_name)
    print(f"\n{'=' * 60}\n  ITERATION {iter_num}/{n_iterations}  (batch: {batch_ids})\n{'=' * 60}")
    t_iter = time.time()
    iter_cost_before = _cost_snapshot(cost_tracker)
    stage_timing, stage_costs = {}, {}

    # ── EXECUTE (K rollouts per task) ──
    print(f"\n  ── EXECUTE (K={K} × {len(batch_ids)} = {K*len(batch_ids)} rollouts) ──")
    t_stage = time.time(); cost_before_stage = _cost_snapshot(cost_tracker)
    per_task_groups, primaries = [], []
    for tid in batch_ids:
        idx = id_to_idx[tid]
        task_workdir = iter_dir / f"task_{tid}"
        task_workdir.mkdir(parents=True, exist_ok=True)
        group = await run_group_execute(
            bench=bench, dataset=dataset, idx=idx, K=K,
            workdir=task_workdir, semaphore=semaphore, skills_dir=skills_dir,
            model=model, project_root=project_root, max_turns=max_turns,
            cost_tracker=cost_tracker, openai_client=openai_client,
        )
        # Attach example for diagnoser context
        for a in group:
            if "example" not in a:
                a["example"] = dataset[idx]
        per_task_groups.append((tid, group))
        primaries.append(pick_primary_assessment(group))
        n_succ = sum(1 for a in group if a["is_correct"])
        gtype = _classify_group(group)
        print(f"    {tid}: K={K}, n_succ={n_succ}, type={gtype}")
    stage_timing["execute"] = round(time.time() - t_stage, 2)
    stage_costs["execute"] = _cost_delta(cost_before_stage, _cost_snapshot(cost_tracker))

    group_evidence_path = build_group_evidence_md(per_task_groups, iter_num, iter_dir)

    # ── DIAGNOSE (group-state-aware dispatch) ──
    print(f"\n  ── DIAGNOSE (group-state dispatch) ──")
    t_stage = time.time(); cost_before_stage = _cost_snapshot(cost_tracker)
    diag_tasks = []
    n_mixed = n_allfail = n_allsucc = 0
    for tid, group in per_task_groups:
        gtype = _classify_group(group)
        if gtype == "mixed":
            diag_tasks.append(run_mixed_group_k_trace_diagnose(
                group, iter_dir, skills_dir, model, project_root,
                semaphore, cost_tracker, skill_name=bench.skill_name))
            n_mixed += 1
        elif gtype == "all_fail":
            diag_tasks.append(run_all_fail_cluster_diagnose(
                group, iter_dir, skills_dir, model, project_root,
                semaphore, cost_tracker, skill_name=bench.skill_name))
            n_allfail += 1
        else:  # all_success
            primary = next((a for a in group if a.get("_rollout_idx") == 0), group[0])
            diag_tasks.append(run_diagnose(
                primary, "contrastive", iter_dir, skills_dir, base_trajectories_dir,
                model, project_root, semaphore, cost_tracker, skill_name=bench.skill_name))
            n_allsucc += 1
    print(f"    dispatched: {n_mixed} mixed, {n_allfail} all_fail, {n_allsucc} all_success")
    diagnoses = await asyncio.gather(*diag_tasks)
    stage_timing["diagnose"] = round(time.time() - t_stage, 2)
    stage_costs["diagnose"] = _cost_delta(cost_before_stage, _cost_snapshot(cost_tracker))

    # TR-lite: tag each diagnosis with evidence_id + tier
    group_types_by_id = {tid: _classify_group(g) for tid, g in per_task_groups}
    evidence_tiers = _assign_evidence_tiers(diagnoses, group_types_by_id)

    batch_diagnoses_path = iter_dir / "batch_diagnoses.md"
    _assemble_v8_diagnoses(diagnoses, primaries, batch_diagnoses_path)

    # All-correct early-stop signal
    all_groups_succ = (n_mixed == 0 and n_allfail == 0)

    # ── MOMENTUM (iter≥2) ──
    patcher_overlay_path = patcher_memory_path = None
    if iter_num >= 2:
        print(f"\n  ── MOMENTUM ──")
        t_stage = time.time(); cost_before_stage = _cost_snapshot(cost_tracker)
        previous_record = output_dir / f"iter_{iter_num - 1}" / "momentum_memory.md"
        momentum_record_path = iter_dir / "momentum_memory.md"
        momentum_overlay_path = iter_dir / "momentum_overlay.md"
        await run_momentum(
            diagnoses_path=batch_diagnoses_path, previous_record_path=previous_record,
            skills_dir=skills_dir, record_output_path=momentum_record_path,
            overlay_output_path=momentum_overlay_path, model=model,
            project_root=project_root, cost_tracker=cost_tracker,
            iter_dir=iter_dir, iter_num=iter_num,
        )
        patcher_overlay_path = momentum_overlay_path
        patcher_memory_path = momentum_record_path
        stage_timing["momentum"] = round(time.time() - t_stage, 2)
        stage_costs["momentum"] = _cost_delta(cost_before_stage, _cost_snapshot(cost_tracker))

    # ── PATCH (with group_evidence + anti-wipe guard) ──
    print(f"\n  ── PATCH (v8: + group_evidence + anti-wipe) ──")
    t_stage = time.time(); cost_before_stage = _cost_snapshot(cost_tracker)

    # Capture pre-patch SKILL.md for anti-wipe revert
    skill_md_path = skills_dir / bench.skill_name / "SKILL.md"
    pre_patch_size = skill_md_path.stat().st_size if skill_md_path.exists() else 0
    pre_patch_text = skill_md_path.read_text(encoding="utf-8") if skill_md_path.exists() else ""

    patch_output = await run_patch(
        batch_diagnoses_path, skills_dir, model, project_root, cost_tracker, iter_dir,
        overlay_path=patcher_overlay_path, momentum_memory_path=patcher_memory_path,
        group_evidence_path=group_evidence_path,
        skill_name=bench.skill_name,
    )

    # Anti-wipe nuclear backstop: revert if patch shrank SKILL.md by > 50%
    # (and pre-patch was substantive, > 50 lines). This is the deterministic
    # guard that makes the paper-grade results reproducible.
    anti_wipe_triggered = False
    if skill_md_path.exists() and pre_patch_size > 1500:
        post_patch_size = skill_md_path.stat().st_size
        if post_patch_size < pre_patch_size * 0.5:
            print(f"  [PATCH-GUARD] WIPE detected: {pre_patch_size}B → {post_patch_size}B "
                  f"({100*(post_patch_size-pre_patch_size)/pre_patch_size:.0f}%). REVERTING.")
            skill_md_path.write_text(pre_patch_text, encoding="utf-8")
            anti_wipe_triggered = True
            stage_costs.setdefault("patch_guard", {})["wipe_reverted"] = True

    stage_timing["patch"] = round(time.time() - t_stage, 2)
    stage_costs["patch"] = _cost_delta(cost_before_stage, _cost_snapshot(cost_tracker))

    # ── MOMENTUM bootstrap (iter_1) ──
    if iter_num == 1:
        t_stage = time.time(); cost_before_stage = _cost_snapshot(cost_tracker)
        momentum_record_path = iter_dir / "momentum_memory.md"
        momentum_overlay_path = iter_dir / "momentum_overlay.md"
        await run_momentum(
            diagnoses_path=batch_diagnoses_path, previous_record_path=momentum_initial_path,
            skills_dir=skills_dir, record_output_path=momentum_record_path,
            overlay_output_path=momentum_overlay_path, model=model,
            project_root=project_root, cost_tracker=cost_tracker,
            iter_dir=iter_dir, iter_num=iter_num,
        )
        stage_timing["momentum_bootstrap"] = round(time.time() - t_stage, 2)
        stage_costs["momentum_bootstrap"] = _cost_delta(cost_before_stage, _cost_snapshot(cost_tracker))

    # ── record iter result ──
    pre_correct = sum(1 for a in primaries if a["is_correct"])
    pre_soft = sum(a["accuracy"]["accuracy"] if isinstance(a.get("accuracy"), dict) else a.get("accuracy", 0) for a in primaries) / len(primaries)
    print(f"\n  ── PATCHED (primaries: {pre_correct}/{len(primaries)} correct, soft {pre_soft:.1%}) ──")

    iter_result = {
        "iteration": iter_num, "batch": batch_ids,
        "result": "all_correct" if all_groups_succ else "patched",
        "n_mixed": n_mixed, "n_all_fail": n_allfail, "n_all_success": n_allsucc,
        "pre_correct": pre_correct, "pre_soft_accuracy": round(pre_soft, 4),
        "K": K, "n_rollouts": K * len(batch_ids),
        "group_classifications": [
            {"id": tid, "group_type": _classify_group(g),
             "n_succ": sum(1 for a in g if a["is_correct"])}
            for tid, g in per_task_groups
        ],
        "duration_s": round(time.time() - t_iter, 2),
        "cost": _cost_delta(iter_cost_before, _cost_snapshot(cost_tracker)),
        "stage_timing": stage_timing, "stage_costs": stage_costs,
        "anti_wipe_triggered": anti_wipe_triggered,
        "skill_md_size_bytes": skill_md_path.stat().st_size if skill_md_path.exists() else 0,
        "skill_md_lines": skill_md_path.read_text(encoding="utf-8").count("\n") if skill_md_path.exists() else 0,
    }
    results["iterations"].append(iter_result)
    results["cumulative_cost"] = _cost_snapshot(cost_tracker)
    _write_workspace(output_dir / "training_results.json", results)
    _log_iteration(output_dir / "iteration_log.md", iter_num, iter_result, primaries, diagnoses)
    _write_iter_summary(iter_dir / "summary.md", iter_num, iter_result, diagnoses)
