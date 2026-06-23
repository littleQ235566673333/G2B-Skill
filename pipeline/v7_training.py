"""v7 training loop = SkillGrad's pipeline + K-rollout group EXECUTE + group_evidence injection.

Differences vs pipeline/training.py:
  1. EXECUTE replaced by per-task run_group_execute (K rollouts).
  2. After EXECUTE, pick a "primary" assessment per task to feed SkillGrad's
     downstream classify/diagnose unchanged.
  3. PATCH receives an additional group_evidence_path (an additive prepend in
     the patcher's user message).

SkillGrad's diagnoser/momentum/patcher PROMPTS are unchanged. The only new
artifact written per iter is group_evidence.md.
"""

from __future__ import annotations
import asyncio, json, shutil, time
from datetime import datetime, timezone
from pathlib import Path

from bench import Bench
from pipeline.diagnoser import assemble_diagnoses, classify_batch, run_diagnose
from pipeline.execution import _write_workspace
from pipeline.group_execution import run_group_execute
from pipeline.momentum import run_momentum
from pipeline.patcher import run_patch
from pipeline.training import _log_iteration, _write_iter_summary, _snapshot_skill
from pipeline.v7_helpers import build_group_evidence_md, pick_primary_assessment
from runners.cost_tracker import CostTracker
from runners.model_dispatch import get_client_for_model


def _cost_snapshot(ct: CostTracker) -> dict:
    return {"input_tokens": ct.input_tokens, "cached_tokens": ct.cached_tokens,
            "output_tokens": ct.output_tokens, "reasoning_tokens": ct.reasoning_tokens,
            "requests": ct.requests, "cost": ct.total_cost}


def _cost_delta(before: dict, after: dict) -> dict:
    return {k: round(after[k] - before[k], 6) if isinstance(after[k], float) else after[k] - before[k]
            for k in before}


async def run_v7_training(
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
    """v7 training loop. See module docstring."""
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
            "K": K, "early_stop": {"all_correct": 4}, "status": "running",
            "iterations": [],
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
    print(f"  v7 training: {n_iterations} iter, K={K}, batch_size={training_config['batch_size']}")
    print(f"  Model: {model} | Skills: {skills_dir}")
    print(f"{'=' * 60}\n")

    for iter_num in range(start_iteration, n_iterations + 1):
        batch_ids = batches[iter_num - 1]
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
            per_task_groups.append((tid, group))
            primaries.append(pick_primary_assessment(group))
            n_succ = sum(1 for a in group if a["is_correct"])
            print(f"    {tid}: K={K}, n_succ={n_succ}, primary=r{primaries[-1].get('_rollout_idx')}")
        stage_timing["execute"] = round(time.time() - t_stage, 2)
        stage_costs["execute"] = _cost_delta(cost_before_stage, _cost_snapshot(cost_tracker))

        group_evidence_path = build_group_evidence_md(per_task_groups, iter_num, iter_dir)

        # ── CLASSIFY (on primaries) ──
        failed, contrastive = classify_batch(primaries)
        n_failed, n_contrastive = len(failed), len(contrastive)
        print(f"\n  ── CLASSIFY: {n_failed} failed, {n_contrastive} contrastive ──")

        if n_failed == 0:
            consecutive_all_correct += 1
            results["iterations"].append({
                "iteration": iter_num, "batch": batch_ids, "result": "all_correct",
                "n_failed": 0, "n_contrastive": n_contrastive,
                "duration_s": round(time.time() - t_iter, 2),
                "cost": _cost_delta(iter_cost_before, _cost_snapshot(cost_tracker)),
                "stage_timing": stage_timing, "stage_costs": stage_costs,
            })
            _write_workspace(output_dir / "training_results.json", results)
            if consecutive_all_correct >= 4:
                print("  EARLY STOP"); break
            if n_contrastive == 0:
                continue
        consecutive_all_correct = 0 if n_failed > 0 else consecutive_all_correct

        # ── DIAGNOSE ──
        print(f"\n  ── DIAGNOSE ──")
        t_stage = time.time(); cost_before_stage = _cost_snapshot(cost_tracker)
        diag_tasks = []
        for a in failed:
            diag_tasks.append(run_diagnose(a, "failure", iter_dir, skills_dir, base_trajectories_dir,
                                           model, project_root, semaphore, cost_tracker, skill_name=bench.skill_name))
        for a in contrastive:
            diag_tasks.append(run_diagnose(a, "contrastive", iter_dir, skills_dir, base_trajectories_dir,
                                           model, project_root, semaphore, cost_tracker, skill_name=bench.skill_name))
        diagnoses = await asyncio.gather(*diag_tasks)
        stage_timing["diagnose"] = round(time.time() - t_stage, 2)
        stage_costs["diagnose"] = _cost_delta(cost_before_stage, _cost_snapshot(cost_tracker))

        batch_diagnoses_path = iter_dir / "batch_diagnoses.md"
        assemble_diagnoses(diagnoses, primaries, batch_diagnoses_path)

        # ── MOMENTUM (iter≥2 pre-patch) ──
        patcher_overlay_path, patcher_memory_path = None, None
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

        # ── PATCH (with group_evidence) ──
        print(f"\n  ── PATCH (v7: + group_evidence) ──")
        t_stage = time.time(); cost_before_stage = _cost_snapshot(cost_tracker)
        await run_patch(
            batch_diagnoses_path, skills_dir, model, project_root, cost_tracker, iter_dir,
            overlay_path=patcher_overlay_path, momentum_memory_path=patcher_memory_path,
            group_evidence_path=group_evidence_path,
        )
        stage_timing["patch"] = round(time.time() - t_stage, 2)
        stage_costs["patch"] = _cost_delta(cost_before_stage, _cost_snapshot(cost_tracker))

        # ── MOMENTUM bootstrap (iter_1 only) ──
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
        pre_soft = sum(a["accuracy"]["accuracy"] for a in primaries) / len(primaries)
        print(f"\n  ── PATCHED (primaries: {pre_correct}/{len(primaries)} correct, soft {pre_soft:.1%}) ──")

        iter_result = {
            "iteration": iter_num, "batch": batch_ids, "result": "patched",
            "n_failed": n_failed, "n_contrastive": n_contrastive,
            "pre_correct": pre_correct, "pre_soft_accuracy": round(pre_soft, 4),
            "K": K, "n_rollouts": K * len(batch_ids),
            "group_classifications": [
                {"id": tid, "group_type": (
                    "all_success" if all(a["is_correct"] for a in g)
                    else "all_fail" if not any(a["is_correct"] for a in g) else "mixed"),
                 "n_succ": sum(1 for a in g if a["is_correct"])}
                for tid, g in per_task_groups
            ],
            "seed_outcomes": {a["id"]: {"pre_correct": a["is_correct"],
                                        "pre_accuracy": a["accuracy"]["accuracy"]} for a in primaries},
            "duration_s": round(time.time() - t_iter, 2),
            "cost": _cost_delta(iter_cost_before, _cost_snapshot(cost_tracker)),
            "stage_timing": stage_timing, "stage_costs": stage_costs,
        }
        results["iterations"].append(iter_result)
        results["cumulative_cost"] = _cost_snapshot(cost_tracker)
        _write_workspace(output_dir / "training_results.json", results)
        _log_iteration(output_dir / "iteration_log.md", iter_num, iter_result, primaries, diagnoses)
        _write_iter_summary(iter_dir / "summary.md", iter_num, iter_result, diagnoses)

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

    print(f"\n{'=' * 60}\n  v7 training complete\n  Final: {final_dir}\n{'=' * 60}")
    return results
