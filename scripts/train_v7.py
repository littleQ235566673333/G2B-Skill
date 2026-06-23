"""CLI: train v7. Mirrors pipeline/training.py main() but calls run_v7_training.

Adds --K (rollouts per task per iter) and forces --batch-schedule fixed-updates
so v7 reuses the same batch construction as v4 / SkillGrad.
"""
from __future__ import annotations
import argparse, asyncio, json, shutil, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bench import get_bench
from data.layout import (base_trajectories_dir_for, normalized_dir_for,
                         run_dir_for, run_id_for, splits_dir_for)
from data.split import (build_fixed_update_training_set, build_training_set,
                        create_split, identify_failures, load_split)
from pipeline.execution import _write_workspace
from pipeline.v7_training import run_v7_training
from scripts.manifest_update import upsert as manifest_upsert


def main() -> None:
    parser = argparse.ArgumentParser(description="v7 training (SkillGrad pipes + K-rollout group + group_evidence injection).")
    parser.add_argument("--bench", choices=["spreadsheet", "wtq"], default="spreadsheet")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--skills-dir", default="seeds")
    parser.add_argument("--results-root", default="results")
    parser.add_argument("--base-trajectories-dir", default=None)
    parser.add_argument("--method", default="g2b-v7")
    parser.add_argument("--model", default="gpt-5.4")
    parser.add_argument("--config-tag", default=None)
    parser.add_argument("--master-seed", type=int, default=0)
    parser.add_argument("--heldout-seed", type=int, default=42)
    parser.add_argument("--training-seed", type=int, default=0)
    parser.add_argument("--n-train", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--batch-schedule", choices=["epoch", "fixed-updates"], default="fixed-updates")
    parser.add_argument("--n-iterations", type=int, default=10)
    parser.add_argument("--batch-seed", type=int, default=0)
    parser.add_argument("--max-turns", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--K", type=int, default=4, help="rollouts per task per iter")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--start-iteration", type=int, default=1)
    args = parser.parse_args()

    results_root = Path(args.results_root)

    if args.data_dir:
        data_dir = Path(args.data_dir)
    elif args.bench == "spreadsheet":
        data_dir = normalized_dir_for(results_root)
    elif args.bench == "wtq":
        data_dir = Path("data/benchmarks/wikitablequestions")
    else:
        raise ValueError(f"unknown bench {args.bench!r}")
    bench = get_bench(args.bench, data_dir=str(data_dir))

    split_dir = splits_dir_for(results_root, args.master_seed, args.heldout_seed, args.bench)
    normalized_dir = normalized_dir_for(results_root)
    base_traj_dir = base_trajectories_dir_for(
        results_root, args.master_seed, args.heldout_seed, args.model, args.bench,
    )
    if args.base_trajectories_dir:
        base_traj_dir = Path(args.base_trajectories_dir).resolve()

    split_path = split_dir / "split.json"
    if not split_path.exists():
        create_split(bench, split_dir, master_seed=args.master_seed,
                     heldout_seed=args.heldout_seed, normalized_dir=normalized_dir)
    split = load_split(split_dir)

    failures_path = base_traj_dir / "failure_ids.json"
    if not failures_path.exists():
        if not base_traj_dir.exists():
            raise FileNotFoundError(f"base trajectories not found at {base_traj_dir}")
        failure_ids, success_ids = identify_failures(base_traj_dir, split["evolution_ids"])
        _write_workspace(failures_path, {"failure_ids": failure_ids, "success_ids": success_ids})
    else:
        failure_ids = json.loads(failures_path.read_text(encoding="utf-8"))["failure_ids"]
    print(f"Loaded {len(failure_ids)} failure IDs from {base_traj_dir}")

    if args.batch_schedule == "fixed-updates":
        training_config = build_fixed_update_training_set(
            failure_ids=failure_ids, training_seed=args.training_seed,
            n_train=args.n_train, batch_size=args.batch_size,
            n_iterations=args.n_iterations, batch_seed=args.batch_seed,
        )
    else:
        training_config = build_training_set(
            failure_ids, args.training_seed, args.n_train, args.batch_size,
        )
    training_config.update({"model": args.model, "max_turns": args.max_turns,
                            "concurrency": args.concurrency, "K": args.K})

    run_id = run_id_for(method=args.method, model=args.model, config_tag=args.config_tag)
    run_dir = run_dir_for(results_root, run_id)
    train_dir = run_dir / "train"
    train_dir.mkdir(parents=True, exist_ok=True)
    _write_workspace(train_dir / "train_set.json", training_config)
    print(f"Run id: {run_id}\nRun dir: {run_dir}")

    started_at = datetime.now(timezone.utc).isoformat()
    config_payload = {
        "run_id": run_id, "method": args.method, "model": args.model,
        "config_tag": args.config_tag, "K": args.K,
        "seeds": {"master_seed": args.master_seed, "heldout_seed": args.heldout_seed,
                  "training_seed": args.training_seed},
        "split_path": str(split_path), "base_trajectories_path": str(base_traj_dir),
        "training_config": {
            "n_train": args.n_train, "batch_size": args.batch_size,
            "batch_schedule": args.batch_schedule, "n_iterations": args.n_iterations,
            "batch_seed": args.batch_seed, "max_turns": args.max_turns,
            "concurrency": args.concurrency, "K": args.K,
        },
        "started": started_at, "status": "running",
    }
    _write_workspace(run_dir / "config.json", config_payload)
    manifest_upsert(results_root, run_dir)

    skills_work_dir = run_dir / "skills"
    if not (skills_work_dir / bench.skill_name / "SKILL.md").exists():
        base = Path(args.skills_dir)
        dest = skills_work_dir / bench.skill_name
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base / bench.skill_name / "SKILL.md", dest / "SKILL.md")
        refs = base / bench.skill_name / "references"
        if refs.exists():
            shutil.copytree(refs, dest / "references")
        print(f"Copied base skill to {skills_work_dir}")

    t_start = time.time()
    results = None
    try:
        results = asyncio.run(run_v7_training(
            bench=bench, skills_dir=skills_work_dir, model=args.model,
            project_root=Path(".").resolve(), output_dir=train_dir,
            base_trajectories_dir=base_traj_dir, training_config=training_config,
            K=args.K, max_turns=args.max_turns, concurrency=args.concurrency,
            interactive=args.interactive, start_iteration=args.start_iteration,
        ))
        final_status = "completed"
    except Exception as exc:
        final_status = f"failed: {exc}"
        raise
    finally:
        config_payload = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
        config_payload["status"] = final_status
        config_payload["completed"] = datetime.now(timezone.utc).isoformat()
        config_payload["elapsed_s"] = round(time.time() - t_start, 1)
        if results is not None:
            iters = results.get("iterations", [])
            config_payload["metrics"] = {
                "n_iterations": len(iters),
                "n_patched": sum(1 for it in iters if it.get("result") == "patched"),
                "n_all_correct": sum(1 for it in iters if it.get("result") == "all_correct"),
                "test_hard": None, "test_cell_acc": None,
            }
            config_payload["cost"] = results.get("cost") or results.get("cumulative_cost")
        _write_workspace(run_dir / "config.json", config_payload)
        manifest_upsert(results_root, run_dir)

    print(f"\nTraining results: {train_dir / 'training_results.json'}")
    print(f"Final skill:      {train_dir / 'final_skill' / bench.skill_name / 'SKILL.md'}")
    print(f"Elapsed:          {round(time.time() - t_start, 1)}s")


if __name__ == "__main__":
    main()
