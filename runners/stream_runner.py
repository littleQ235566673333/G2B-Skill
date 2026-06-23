"""Shared executor+grader stream runner for evaluation and base trajectories.

Bench-aware (post-A7/A8 refactor 2026-06-16). All file-path
construction and grading is delegated to a Bench instance via
``bench.prepare_seed_data`` / ``bench.assess``. Multi-test-case mode
(SpreadsheetBench-only legacy) is dropped — every record is one task,
one execution.

Output formats (unchanged):
  - "base_trajectories": collect base-skill trajectories on the
    evolution pool; emit per-task ``assessment.json`` + ``failure_ids.json``.
  - "eval": evaluate a trained skill on a held-out split; emit
    ``eval_summary.json``.
  - "training": same as eval but writes per-task ``evolve_<id>/``
    workdirs (used by the training loop's batch executor).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from dotenv import load_dotenv

from bench import Bench, get_bench
from data.layout import (
    base_trajectories_dir_for,
    normalized_dir_for,
    run_dir_for,
    run_id_for,
    splits_dir_for,
)
from data.split import identify_failures, load_split
from pipeline.execution import run_execute
from runners.cost_tracker import CostTracker
from runners.model_dispatch import get_client_for_model
from runners.soffice import find_soffice, install_soffice_wrapper
from runners.trajectory_logger import save_merged_trace
from scripts.manifest_update import upsert as manifest_upsert

load_dotenv()


# ─── small JSON helper (atomic write) ───────────────────────────────────

def _save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.rename(path)


# ─── aggregates (unchanged) ─────────────────────────────────────────────

def _eval_aggregate(records: dict[int, dict], total: int) -> dict:
    graded = [r for r in records.values() if r.get("status") == "graded"]
    all_scored = [r for r in records.values() if "hard_score" in r]
    pass_count = sum(1 for r in graded if r.get("hard_score") == 1.0)
    pending = sum(1 for r in records.values() if r.get("status") in {"grade_pending", "grading"})
    executing = sum(1 for r in records.values() if r.get("status") == "executing")
    retry_needed = sum(1 for r in records.values() if r.get("status") == "retry_needed")
    stopped = sum(1 for r in records.values() if r.get("status") == "stopped_early")
    not_started = total - len(records)
    best_possible = pass_count + pending + executing + not_started
    n_scored = len(all_scored)
    return {
        "n_seeds": n_scored,
        "mean_cell_accuracy": round(sum(r.get("cell_accuracy", 0.0) for r in all_scored) / n_scored, 4) if n_scored else 0.0,
        "mean_hard": round(sum(r.get("hard_score", 0.0) for r in all_scored) / n_scored, 4) if n_scored else 0.0,
        "n_perfect": sum(1 for r in all_scored if r.get("hard_score") == 1.0),
        "n_total": total,
        "n_records": len(records),
        "n_scored": n_scored,
        "n_graded": len(graded),
        "n_pass_graded": pass_count,
        "mean_cell_graded": round(sum(r.get("cell_accuracy", 0.0) for r in graded) / len(graded), 4) if graded else 0.0,
        "mean_hard_graded": round(pass_count / len(graded), 4) if graded else 0.0,
        "conservative_hard_if_pending_zero": round(pass_count / total, 4) if total else 0.0,
        "best_possible_hard_count": best_possible,
        "best_possible_hard": round(best_possible / total, 4) if total else 0.0,
        "pending_outputs": pending,
        "executing": executing,
        "retry_needed": retry_needed,
        "stopped_early": stopped,
        "not_started": not_started,
    }


def _base_aggregate(results: list[dict], total: int) -> dict:
    done = len(results)
    passed = sum(1 for r in results if r.get("is_correct"))
    return {
        "n_done": done,
        "n_seeds": total,
        "n_perfect": passed,
        "n_failed": done - passed,
        "hard_score": round(passed / done, 4) if done else 0.0,
        "mean_cell_accuracy": round(sum(r.get("cell_accuracy", 0.0) for r in results) / done, 4) if done else 0.0,
    }


def _summary(output_format: str, records: dict[int, dict], config: dict, cost: CostTracker, t0: float, status: str) -> dict:
    total = config["total"]
    if output_format == "base_trajectories":
        results = sorted(records.values(), key=lambda r: str(r.get("id", "")))
        return {
            "config": config,
            "aggregate": _base_aggregate(results, total),
            "status": status,
            "completed": len(results),
            "total": total,
            "elapsed": round(time.time() - t0, 1),
            "cost": cost.to_dict(),
            "results": results,
        }
    results = sorted(records.values(), key=lambda r: r.get("index", 999999))
    return {
        "config": config,
        "status": status,
        "completed": len(records),
        "completed_records": len(records),
        "total": total,
        "aggregate": _eval_aggregate(records, total),
        "cost": cost.to_dict(),
        "elapsed": round(time.time() - t0, 1),
        "results": results,
    }


# ─── per-record execute (bench-aware, single test case) ─────────────────

async def _execute_record(
    bench: Bench,
    dataset: list[dict],
    idx: int,
    skill_dir: Path,
    model: str,
    project_root: Path,
    workdir: Path,
    max_turns: int,
    cost: CostTracker,
    output_format: str,
    openai_client,
) -> dict:
    """Run the executor on one task and return a record dict.

    Per-task workdir is named according to ``output_format``:
      - "base_trajectories": ``workdir/<id>/``
      - "training":          ``workdir/evolve_<id>/``
      - "eval":              ``workdir/eval_<id>_tc1/``  (kept for layout compat)

    The bench owns the input file copy + task_str + ground_truth via
    ``bench.prepare_seed_data``. Single test case per record.
    """
    example = dataset[idx]
    ex_id = str(example["id"])

    if output_format == "base_trajectories":
        task_dir_name = ex_id
    elif output_format == "training":
        task_dir_name = f"evolve_{ex_id}"
    else:  # eval
        task_dir_name = f"eval_{ex_id}_tc1"

    seed_data = bench.prepare_seed_data(dataset, idx, workdir, task_dir_name=task_dir_name)
    desired = Path(seed_data["task_workdir"])

    error_msg = ""
    exec_result = None
    start = time.time()
    try:
        exec_result = await run_execute(
            seed_data,
            asyncio.Semaphore(1),  # caller already gates concurrency at the worker level
            skill_dir,
            model,
            project_root,
            max_turns,
            0,  # round 0
            cost,
            openai_client,
            skill_name=bench.skill_name,
        )
    except Exception as exc:
        error_msg = str(exc)
        print(f"  [EXEC {ex_id}] ERROR: {exc}")

    record = {
        "index": idx,
        "id": ex_id,
        "instruction": str(example.get("instruction", ""))[:300],
        "status": "grade_pending" if exec_result is not None else "retry_needed",
        "retry_reason": "" if exec_result is not None else "exec_error",
        "exec_errors": [error_msg] if error_msg else [],
        "elapsed": round(time.time() - start, 1),
        "cost": exec_result.get("cost", {}) if exec_result else {},
        "_seed_data": seed_data,        # passed to grader
        "_exec_result": exec_result,    # passed to grader
        "task_dir": str(desired),
    }
    if exec_result is None:
        record.update({
            "cell_accuracy": 0.0, "hard_score": 0.0,
            "match_count": 0, "total_count": 0,
        })
    return record


# ─── per-record grade (bench-aware) ─────────────────────────────────────

async def _grade_record(
    record: dict,
    bench: Bench,
    output_format: str,
) -> dict:
    """Grade a record by delegating to ``bench.assess``.

    Writes per-task ``assessment.json`` + ``cell_comparison.txt`` +
    merged trace at ``trace.jsonl`` in the historical layout the
    base_trajectories failure-id detection relies on.
    """
    seed_data = record.pop("_seed_data", None)
    exec_result = record.pop("_exec_result", None)
    task_dir = Path(record["task_dir"])

    if exec_result is None or seed_data is None:
        return {**record, "cell_accuracy": 0.0, "hard_score": 0.0,
                "match_count": 0, "total_count": 0, "status": "retry_needed"}

    try:
        assessment = await asyncio.to_thread(
            bench.assess, seed_data, exec_result, 0,
        )
    except Exception as exc:
        return {**record, "cell_accuracy": 0.0, "hard_score": 0.0,
                "match_count": 0, "total_count": 0,
                "status": "retry_needed",
                "retry_reason": f"grading_exception: {exc}"}

    acc = assessment["accuracy"]
    is_correct = bool(assessment["is_correct"])
    print(
        f"  [GRADE idx={record['index']} id={record['id']}] "
        f"{acc['match_count']}/{acc['total_count']} ({acc['accuracy']:.1%})"
    )

    # Historical-compat artifact files at the record's task_dir
    _save_json(task_dir / "assessment.json", {
        "id": record["id"],
        "cell_accuracy": acc["accuracy"],
        "match_count": acc["match_count"],
        "total_count": acc["total_count"],
        "is_correct": is_correct,
    })
    try:
        (task_dir / "cell_comparison.txt").write_text(
            assessment.get("cell_comparison", ""), encoding="utf-8",
        )
    except Exception as exc:
        (task_dir / "cell_comparison.txt").write_text(
            f"(cell_comparison failed: {exc})", encoding="utf-8",
        )
    raw_trace = task_dir / "exec_r0.jsonl"
    if raw_trace.exists():
        try:
            save_merged_trace(raw_trace, task_dir / "trace.jsonl")
        except Exception:
            pass

    graded = dict(record)
    graded["status"] = "graded"
    graded["cell_accuracy"] = acc["accuracy"]
    graded["hard_score"] = 1.0 if is_correct else 0.0
    graded["match_count"] = acc["match_count"]
    graded["total_count"] = acc["total_count"]
    if output_format == "base_trajectories":
        graded["is_correct"] = is_correct
    return graded


# ─── orchestration: queues + workers + summary saver ────────────────────

async def run_stream(
    indices: list[int],
    bench: Bench,
    dataset: list[dict],
    skill_dir: Path,
    model: str,
    workdir: Path,
    *,
    project_root: Path | None = None,
    max_turns: int = 30,
    executor_concurrency: int = 3,
    grader_concurrency: int = 1,
    grade_queue_max: int = 20,
    on_record_complete: Callable[[dict], None] | None = None,
    output_format: Literal["eval", "base_trajectories", "training"] = "eval",
    soffice_lock_path: Path | None = None,
    use_soffice_wrapper: bool = True,
    stop_if_best_below: int | None = None,
    failure_ids_dir: Path | None = None,
) -> dict:
    """Run executor + grader workers over a list of dataset indices."""
    project_root = project_root or Path.cwd()
    workdir.mkdir(parents=True, exist_ok=True)
    summary_name = "summary.json" if output_format == "base_trajectories" else "eval_summary.json"
    summary_path = workdir / summary_name
    total = len(indices)

    # SpreadsheetBench needs soffice; WTQ doesn't. Install wrapper only
    # when relevant — WTQ runs skip the warning.
    if bench.name == "spreadsheet":
        if soffice_lock_path is None:
            soffice_lock_path = Path("/tmp/skillgrad_soffice.lock")
        if use_soffice_wrapper:
            tools_dir = install_soffice_wrapper(workdir, soffice_lock_path)
            if tools_dir:
                print(f"  Installed soffice wrapper in {tools_dir}")
            else:
                print("  WARNING: LibreOffice/soffice not found; grading may fail.")
        else:
            real_soffice = find_soffice()
            if real_soffice:
                import os
                os.environ["SE_PIPELINE_REAL_SOFFICE"] = real_soffice
                os.environ["SE_PIPELINE_SOFFICE_LOCK"] = str(soffice_lock_path)

    config = {
        "mode": output_format,
        "bench": bench.name,
        "model": model,
        "skills_dir": str(skill_dir),
        "data_dir": str(bench.data_dir),
        "indices": indices,
        "max_turns": max_turns,
        "executor_concurrency": executor_concurrency,
        "grader_concurrency": grader_concurrency,
        "grade_queue_max": grade_queue_max,
        "soffice_lock_path": str(soffice_lock_path) if soffice_lock_path else None,
        "use_soffice_wrapper": use_soffice_wrapper,
        "stop_if_best_below": stop_if_best_below,
        "total": total,
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    }

    records: dict[int, dict] = {}
    if output_format == "base_trajectories":
        for idx in indices:
            ex_id = str(dataset[idx]["id"])
            ap = workdir / ex_id / "assessment.json"
            if ap.exists():
                records[idx] = json.loads(ap.read_text(encoding="utf-8")) | {"index": idx}

    cost = CostTracker(model)
    openai_client = get_client_for_model(model)
    t0 = time.time()
    _save_json(summary_path, _summary(output_format, records, config, cost, t0, "running"))

    pending = [idx for idx in indices if idx not in records]
    exec_queue: asyncio.Queue[int | None] = asyncio.Queue()
    grade_queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=grade_queue_max)
    stop_event = asyncio.Event()
    for idx in pending:
        exec_queue.put_nowait(idx)

    def save(status: str = "running") -> dict:
        summary = _summary(output_format, records, config, cost, t0, status)
        _save_json(summary_path, summary)
        agg = summary["aggregate"]
        if output_format == "base_trajectories":
            print(f"  [{summary['completed']}/{total}] hard={agg.get('hard_score', 0):.1%} cell={agg.get('mean_cell_accuracy', 0):.1%}")
        else:
            target = f" target>{stop_if_best_below - 1}" if stop_if_best_below else ""
            print(
                "  [MONITOR] "
                f"graded={agg['n_graded']}/{total} pass={agg['n_pass_graded']} "
                f"graded_hard={agg.get('mean_hard_graded', 0):.1%} "
                f"cell={agg.get('mean_cell_graded', 0):.1%} "
                f"pending={agg.get('pending_outputs', 0)} "
                f"executing={agg.get('executing', 0)} "
                f"retry_needed={agg.get('retry_needed', 0)} "
                f"best={agg['best_possible_hard_count']}/{total}"
                f"{target} cost=${cost.total_cost:.4f}"
            )
            if stop_if_best_below is not None and agg["best_possible_hard_count"] < stop_if_best_below:
                stop_event.set()
        return summary

    async def executor_worker(worker_id: int) -> None:
        while True:
            idx = await exec_queue.get()
            if idx is None:
                exec_queue.task_done()
                return
            ex_id = str(dataset[idx]["id"])
            if stop_event.is_set() and output_format != "base_trajectories":
                records[idx] = {"index": idx, "id": ex_id, "status": "stopped_early",
                                "cell_accuracy": 0.0, "hard_score": 0.0,
                                "match_count": 0, "total_count": 0,
                                "elapsed": 0, "cost": {}}
                exec_queue.task_done()
                save()
                continue
            records[idx] = {"index": idx, "id": ex_id, "status": "executing"}
            save()
            print(f"  [EXEC worker={worker_id}] idx={idx} id={ex_id}")
            try:
                record = await _execute_record(
                    bench, dataset, idx, skill_dir, model, project_root,
                    workdir, max_turns, cost, output_format, openai_client,
                )
            except Exception as exc:
                record = {"index": idx, "id": ex_id, "status": "retry_needed",
                          "retry_reason": f"executor_exception: {exc}",
                          "cell_accuracy": 0.0, "hard_score": 0.0,
                          "match_count": 0, "total_count": 0,
                          "elapsed": 0, "cost": {}}
            # Strip private (_-prefixed) keys before persisting — those
            # carry Path / Logger objects intended only for the grader.
            records[idx] = {k: v for k, v in record.items() if not k.startswith("_")}
            save()
            if record.get("status") == "grade_pending":
                await grade_queue.put(record)
            exec_queue.task_done()

    async def grader_worker(worker_id: int) -> None:
        while True:
            record = await grade_queue.get()
            if record is None:
                grade_queue.task_done()
                return
            idx = record["index"]
            records[idx] = {**records[idx], "status": "grading"}
            save()
            print(f"  [GRADE worker={worker_id}] idx={idx} id={record['id']}")
            graded = await _grade_record(record, bench, output_format)
            records[idx] = graded
            if on_record_complete:
                on_record_complete(graded)
            grade_queue.task_done()
            save()

    exec_workers = [asyncio.create_task(executor_worker(i + 1)) for i in range(executor_concurrency)]
    grade_workers = [asyncio.create_task(grader_worker(i + 1)) for i in range(grader_concurrency)]
    await exec_queue.join()
    for _ in exec_workers:
        exec_queue.put_nowait(None)
    await asyncio.gather(*exec_workers)
    await grade_queue.join()
    for _ in grade_workers:
        await grade_queue.put(None)
    await asyncio.gather(*grade_workers)

    final_status = "stopped_early" if stop_event.is_set() else "completed"
    summary = save(final_status)
    agg = summary["aggregate"]
    elapsed = summary["elapsed"]

    w = 78
    print(f"\n{'=' * w}")
    if output_format == "base_trajectories":
        print(f"  BASE TRAJECTORIES ({final_status}, {elapsed:.0f}s, bench={bench.name})")
        print(f"{'=' * w}")
        print(
            f"  Done: {summary['completed']}/{total}  |  "
            f"hard: {agg.get('hard_score', 0):.1%}  |  "
            f"cell: {agg.get('mean_cell_accuracy', 0):.1%}  |  "
            f"perfect: {agg.get('n_perfect', 0)}/{summary['completed']}"
        )
    else:
        print(f"  STREAM EVALUATION RESULTS ({final_status}, {elapsed:.0f}s, bench={bench.name})")
        print(f"{'=' * w}")
        print(
            f"  Graded: {agg['n_graded']}/{total} | "
            f"Pass: {agg['n_pass_graded']} | "
            f"Graded hard: {agg.get('mean_hard_graded', 0):.1%} | "
            f"Cell (graded): {agg.get('mean_cell_graded', 0):.1%}"
        )
    print(f"  Cost: ${cost.total_cost:.4f}")
    print(f"{'=' * w}")

    if output_format == "base_trajectories":
        ids = [str(dataset[idx]["id"]) for idx in indices]
        failure_ids, success_ids = identify_failures(workdir, ids)
        fid_dir = failure_ids_dir if failure_ids_dir is not None else workdir.parent
        _save_json(
            fid_dir / "failure_ids.json",
            {"failure_ids": failure_ids, "success_ids": success_ids,
             "summary": summary["aggregate"]},
        )
        print(f"  Failure IDs saved: {fid_dir / 'failure_ids.json'}")
    print(f"  Results saved to {summary_path}")
    return summary


# ─── helpers ─────────────────────────────────────────────────────────────

def _maybe_update_run_metrics(workdir: Path, summary: dict, results_root: Path) -> None:
    """If ``workdir`` is ``<run_dir>/eval`` and a sibling ``config.json``
    exists, patch metrics into it and upsert the manifest. Silent no-op
    otherwise.
    """
    run_dir = workdir.parent
    config_path = run_dir / "config.json"
    if workdir.name != "eval" or not config_path.exists():
        return
    config = json.loads(config_path.read_text(encoding="utf-8"))
    metrics = config.get("metrics") or {}
    agg = summary.get("aggregate", {})
    metrics["test_hard"] = agg.get("mean_hard_graded") or agg.get("hard_score")
    metrics["test_cell_acc"] = agg.get("mean_cell_graded") or agg.get("mean_cell_accuracy")
    metrics["eval_n_graded"] = agg.get("n_graded")
    metrics["eval_n_total"] = summary.get("total")
    config["metrics"] = metrics
    if config.get("status") == "running":
        config["status"] = "completed"
    config["eval_completed"] = datetime.now(timezone.utc).isoformat()
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest_upsert(results_root, run_dir)


# ─── CLI ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Bench-aware stream runner")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_runtime(p):
        p.add_argument("--max-turns", type=int, default=30)
        p.add_argument("--executor-concurrency", type=int, default=3)
        p.add_argument("--grader-concurrency", type=int, default=1)
        p.add_argument("--grade-queue-max", type=int, default=20)
        p.add_argument("--soffice-lock-path", default="/tmp/skillgrad_soffice.lock")

    def add_bench(p):
        p.add_argument("--bench", choices=["spreadsheet", "wtq", "searchqa", "livemath", "officeqa"], default="spreadsheet")
        p.add_argument("--data-dir", default=None,
                       help="Bench dataset dir. Defaults: "
                            "spreadsheet→<results-root>/normalized, "
                            "wtq→data/benchmarks/wikitablequestions, "
                            "searchqa→data/benchmarks/searchqa, "
                            "livemath→data/benchmarks/livemathbench, "
                            "officeqa→data/benchmarks/officeqa.")

    # eval
    p_eval = sub.add_parser("eval")
    add_runtime(p_eval)
    add_bench(p_eval)
    p_eval.add_argument("--skill-dir", required=True)
    p_eval.add_argument("--output-dir", required=True)
    p_eval.add_argument("--model", required=True)
    p_eval.add_argument("--master-seed", type=int, default=0)
    p_eval.add_argument("--heldout-seed", type=int, default=42)
    p_eval.add_argument("--results-root", default="results")
    p_eval.add_argument("--split", default="test_indices")
    p_eval.add_argument("--stop-if-best-below", type=int)

    # base-trajectories
    p_base = sub.add_parser("base-trajectories")
    add_runtime(p_base)
    add_bench(p_base)
    p_base.add_argument("--results-root", default="results")
    p_base.add_argument("--master-seed", type=int, default=0)
    p_base.add_argument("--heldout-seed", type=int, default=42)
    p_base.add_argument("--model", default="gpt-5.4")
    p_base.add_argument("--skills-dir", default="seeds")
    p_base.add_argument("--output-dir", default=None)
    p_base.add_argument("--ids", nargs="+", default=None)

    args = parser.parse_args()

    results_root = Path(args.results_root)

    # Resolve data_dir per bench
    if args.data_dir:
        data_dir = Path(args.data_dir)
    elif args.bench == "spreadsheet":
        data_dir = normalized_dir_for(results_root)
    elif args.bench == "wtq":
        data_dir = Path("data/benchmarks/wikitablequestions")
    elif args.bench == "searchqa":
        data_dir = Path("data/benchmarks/searchqa")
    elif args.bench == "livemath":
        data_dir = Path("data/benchmarks/livemathbench")
    elif args.bench == "officeqa":
        data_dir = Path("data/benchmarks/officeqa")
    else:
        raise ValueError(f"unknown bench {args.bench!r}")

    if not data_dir.exists():
        raise FileNotFoundError(
            f"Dataset dir {data_dir} not found. "
            f"For spreadsheet, run `python -m data.split split ...`. "
            f"For wtq, run `python -m data.benchmarks.build_wtq_dataset`. "
            f"For searchqa, run `python -m data.benchmarks.build_searchqa_dataset`. "
            f"For livemath, run `python -m data.benchmarks.build_livemath_dataset`. "
            f"For officeqa, run `python -m data.benchmarks.build_officeqa_dataset`."
        )

    bench = get_bench(args.bench, data_dir=str(data_dir))
    dataset = bench.load_dataset()

    # Resolve split (bench-keyed when not spreadsheet — see A9)
    split_dir = splits_dir_for(results_root, args.master_seed, args.heldout_seed, args.bench)
    if not (split_dir / "split.json").exists():
        raise FileNotFoundError(
            f"Canonical split not found at {split_dir}. Run "
            f"`python -m data.split split --bench {args.bench} "
            f"--master-seed {args.master_seed} --heldout-seed "
            f"{args.heldout_seed}` first."
        )
    split = load_split(split_dir)

    if args.command == "base-trajectories":
        id_to_idx = {str(s["id"]): i for i, s in enumerate(dataset)}
        indices = [id_to_idx[str(tid)] for tid in split["evolution_ids"]]
        if args.ids:
            requested = {str(t) for t in args.ids}
            pool = {str(tid) for tid in split["evolution_ids"]}
            unknown = requested - pool
            if unknown:
                raise ValueError(
                    f"--ids contains task IDs not in the evolution pool: "
                    f"{sorted(unknown)}"
                )
            indices = [i for i in indices if str(dataset[i]["id"]) in requested]
        if args.output_dir:
            workdir = Path(args.output_dir)
        else:
            workdir = base_trajectories_dir_for(
                results_root, args.master_seed, args.heldout_seed, args.model, args.bench,
            )
        output_format = "base_trajectories"
        skill_dir = Path(args.skills_dir)
        stop_if_best_below = None
        failure_ids_dir = workdir if args.output_dir else None
    else:
        skill_dir = Path(args.skill_dir)
        if not (skill_dir / bench.skill_name).exists():
            raise FileNotFoundError(
                f"No {bench.skill_name!r} skill found under {skill_dir} "
                f"(expected {skill_dir}/{bench.skill_name}/SKILL.md)."
            )
        try:
            indices = [int(i) for i in split[args.split]]
        except KeyError:
            raise KeyError(
                f"Split key '{args.split}' not found in {split_dir / 'split.json'}. "
                f"Available: {sorted(k for k in split if k.endswith('_indices'))}"
            )
        workdir = Path(args.output_dir)
        output_format = "eval"
        stop_if_best_below = args.stop_if_best_below
        failure_ids_dir = None

    summary = asyncio.run(run_stream(
        indices=indices,
        bench=bench,
        dataset=dataset,
        skill_dir=skill_dir,
        model=args.model,
        workdir=workdir,
        project_root=Path(".").resolve(),
        max_turns=args.max_turns,
        executor_concurrency=args.executor_concurrency,
        grader_concurrency=args.grader_concurrency,
        grade_queue_max=args.grade_queue_max,
        output_format=output_format,
        soffice_lock_path=Path(args.soffice_lock_path) if args.bench == "spreadsheet" else None,
        stop_if_best_below=stop_if_best_below,
        failure_ids_dir=failure_ids_dir,
    ))

    if args.command == "eval":
        _maybe_update_run_metrics(workdir, summary, results_root)


if __name__ == "__main__":
    main()
