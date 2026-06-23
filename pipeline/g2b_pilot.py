"""Pilot: measure mixed-group rate on K rollouts per task.

Loads a skill (default: SkillGrad's trained ``final_skill``) and runs K
rollouts per task on a chosen task pool. Reports the
mixed/all-fail/all-success distribution and per-group reward variance.

Pre-Phase-1 feasibility gate from §7.2 of the framework doc: if mixed-
group-rate is too low, group-relative diagnosis won't have enough
signal and we need to revisit diversity injection before implementing
Phase 2+.

Bench-aware (post-A7 refactor): pass ``--bench {spreadsheet,wtq}``.

Usage:
    bash scripts/g2b_pilot.sh                              # spreadsheet bench, defaults
    BENCH=wtq bash scripts/g2b_pilot.sh                    # wtq bench
    SKILL_DIR=seeds bash scripts/g2b_pilot.sh              # pilot on seed skill
    K=8 bash scripts/g2b_pilot.sh                          # K=8 ablation
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from pathlib import Path

from bench import get_bench
from data.layout import (
    base_trajectories_dir_for,
    splits_dir_for,
)
from data.split import load_split
from pipeline.execution import _write_workspace
from pipeline.group_execution import (
    classify_group,
    group_summary,
    run_group_execute,
)
from runners.cost_tracker import CostTracker
from runners.model_dispatch import get_client_for_model


async def main_async(args):
    results_root = Path(args.results_root)
    bench = get_bench(args.bench, data_dir=args.data_dir)

    # ── Resolve task pool ─────────────────────────────────────────────────
    split_dir = splits_dir_for(results_root, args.master_seed, args.heldout_seed, args.bench)
    if (split_dir / "split.json").exists():
        split = load_split(split_dir)
        print(f"Split: {split['n_evolution']} evolution, {split['n_test']} test")
    else:
        split = None
        print(f"(no canonical split at {split_dir} — using --task-pool all from dataset)")

    if args.task_pool == "failed":
        base_traj_dir = base_trajectories_dir_for(
            results_root, args.master_seed, args.heldout_seed, args.model, args.bench,
        )
        failures_path = base_traj_dir.parent / "failure_ids.json"
        if not failures_path.exists():
            failures_path = base_traj_dir / "failure_ids.json"
        if not failures_path.exists():
            raise FileNotFoundError(
                f"--task-pool failed but no failure_ids.json at {failures_path}. "
                f"Run base_traj first or pass --task-pool all."
            )
        with open(failures_path) as f:
            failure_data = json.load(f)
        task_ids = failure_data["failure_ids"]
        print(f"Loaded {len(task_ids)} failure IDs from {failures_path}")
    elif args.task_pool == "all":
        if split is None:
            dataset_full = bench.load_dataset()
            task_ids = [str(e["id"]) for e in dataset_full]
        else:
            task_ids = split["evolution_ids"]
    else:
        raise ValueError(f"unknown task_pool {args.task_pool}")

    if args.n_tasks > 0:
        task_ids = task_ids[: args.n_tasks]
    print(f"Pilot will run K={args.K} rollouts on {len(task_ids)} tasks")

    # ── Set up ────────────────────────────────────────────────────────────
    dataset = bench.load_dataset()
    id_to_idx = {str(e["id"]): i for i, e in enumerate(dataset)}

    pilot_dir = Path(args.output_dir)
    pilot_dir.mkdir(parents=True, exist_ok=True)

    cost_tracker = CostTracker(args.model)
    semaphore = asyncio.Semaphore(args.concurrency)
    openai_client = get_client_for_model(args.model)

    skills_dir = Path(args.skill_dir).resolve()
    expected_skill = skills_dir / bench.skill_name / "SKILL.md"
    if not expected_skill.exists():
        raise FileNotFoundError(
            f"Expected skill at {expected_skill} — got skill_dir={skills_dir}, "
            f"bench.skill_name={bench.skill_name!r}"
        )
    print(f"Using bench={bench.name} skill={bench.skill_name} from {skills_dir}")

    # ── Run groups (one task at a time — group-internal parallelism via
    # semaphore. Multi-group parallelism is easy later by dispatching all
    # groups to asyncio.gather.) ──────────────────────────────────────────
    t0 = time.time()
    all_summaries = []
    for gi, tid in enumerate(task_ids):
        if tid not in id_to_idx:
            print(f"  [warn] task {tid} not in dataset")
            continue
        idx = id_to_idx[tid]
        group_workdir = pilot_dir / f"group_{tid}"
        group_workdir.mkdir(parents=True, exist_ok=True)

        print(f"\n[group {gi+1}/{len(task_ids)}] task {tid}  K={args.K}")
        group_assessments = await run_group_execute(
            bench, dataset, idx, args.K,
            workdir=group_workdir,
            semaphore=semaphore,
            skills_dir=skills_dir,
            model=args.model,
            project_root=Path(".").resolve(),
            max_turns=args.max_turns,
            cost_tracker=cost_tracker,
            openai_client=openai_client,
        )
        gs = group_summary(group_assessments)
        gs["task_id"] = tid
        all_summaries.append(gs)
        print(
            f"  → {gs['group_type']:>12s}  "
            f"n_success={gs['n_success']}/{gs['K']}  "
            f"soft_range={gs['soft_acc_range']:.2f}"
        )
        _write_workspace(pilot_dir / "group_summaries.json", all_summaries)

    elapsed = round(time.time() - t0, 1)

    # ── Aggregate ─────────────────────────────────────────────────────────
    type_counter = Counter(s["group_type"] for s in all_summaries)
    n = len(all_summaries) or 1
    print("\n" + "=" * 60)
    print(f"  PILOT RESULTS  ({elapsed}s, cost=${cost_tracker.total_cost:.2f})")
    print("=" * 60)
    print(f"  Bench: {bench.name}  |  Tasks: {n}  |  K: {args.K}  |  Skill: {skills_dir}")
    for t in ("mixed", "all_fail", "all_success"):
        c = type_counter.get(t, 0)
        print(f"  {t:>12s}: {c:>3d}  ({c/n:.1%})")

    mixed = [s for s in all_summaries if s["group_type"] == "mixed"]
    if mixed:
        ranges = sorted(s["soft_acc_range"] for s in mixed)
        med = ranges[len(ranges) // 2]
        print(f"\n  Mixed-group soft_acc_range: "
              f"min={ranges[0]:.2f}  median={med:.2f}  max={ranges[-1]:.2f}")

    final = {
        "config": vars(args),
        "elapsed_s": elapsed,
        "n_tasks": n,
        "type_counts": dict(type_counter),
        "type_rates": {t: type_counter.get(t, 0) / n for t in ("mixed", "all_fail", "all_success")},
        "group_summaries": all_summaries,
    }
    out_path = pilot_dir / "pilot_results.json"
    _write_workspace(out_path, final)
    print(f"\n  Saved: {out_path}")


def main():
    p = argparse.ArgumentParser(description="Mixed-group-rate pilot")
    p.add_argument("--bench", choices=["spreadsheet", "wtq"], default="spreadsheet")
    p.add_argument("--data-dir", required=True,
                   help="Bench dataset directory (e.g., data/benchmarks/spreadsheetbench)")
    p.add_argument("--skill-dir", required=True,
                   help="Directory containing <skill_name>/SKILL.md (skill_name comes from the bench)")
    p.add_argument("--task-pool", choices=["failed", "all"], default="failed")
    p.add_argument("--n-tasks", type=int, default=20,
                   help="Subsample first N tasks (0 = use all). Default 20 for cheap pilot.")
    p.add_argument("--K", type=int, default=4)
    p.add_argument("--model", default="gpt-5.4")
    p.add_argument("--master-seed", type=int, default=0)
    p.add_argument("--heldout-seed", type=int, default=42)
    p.add_argument("--results-root", default="results")
    p.add_argument("--output-dir", default="results/pilot/g2b_mixed_rate")
    p.add_argument("--max-turns", type=int, default=30)
    p.add_argument("--concurrency", type=int, default=4)
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
