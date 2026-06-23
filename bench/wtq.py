"""WikiTableQuestions adapter — Bench protocol implementation for WTQ.

Mirrors the SpreadsheetBench adapter's shape so the rest of the
pipeline (run_execute, training loop, diagnoser, momentum, patcher)
treats WTQ uniformly.

On-disk layout expected at ``data_dir``::

    data_dir/
    ├── dataset.json          # built by data/benchmarks/build_wtq_dataset.py
    └── csv/
        └── <XXX>-csv/
            └── <NNN>.csv     # raw WTQ tables

dataset.json entry shape::

    {
      "id":            "nt-0",
      "instruction":   "what was the last year ...",
      "table_csv":     "csv/204-csv/590.csv",   # relative to data_dir
      "answer_values": ["2004"]
    }

Per-task workspace
------------------
Each task gets ``task_workdir/evolve_<id>/``::

    input.csv     # copied from data_dir/<table_csv>
    output.txt    # the executor writes its answer(s) here, one per line

The seed skill at ``seeds/wtq/SKILL.md`` instructs the executor to
write to ``output.txt``; assess() reads it back and compares to
``answer_values`` via the Stanford-style normalized matcher.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from evaluators.wtq_compare import compute_accuracy, format_comparison
from pipeline.execution import _write_workspace
from runners.trajectory_logger import build_execution_trace


@dataclass
class WTQBench:
    """WikiTableQuestions bench."""

    data_dir: Path
    name: str = "wtq"
    skill_name: str = "wtq"

    # ─── dataset I/O ────────────────────────────────────────────────────

    def load_dataset(self) -> list[dict]:
        with open(self.data_dir / "dataset.json", encoding="utf-8") as f:
            return json.load(f)

    # ─── per-task workspace ─────────────────────────────────────────────

    def prepare_seed_data(
        self, dataset: list[dict], idx: int, workdir: Path,
        task_dir_name: str | None = None,
    ) -> dict:
        example = dataset[idx]
        ex_id = example["id"]

        table_path = self.data_dir / example["table_csv"]
        if not table_path.exists():
            raise FileNotFoundError(
                f"WTQ table not found: {table_path} "
                f"(referenced by example {ex_id!r})"
            )

        task_workdir = workdir / (task_dir_name or f"evolve_{ex_id}")
        task_workdir.mkdir(parents=True, exist_ok=True)
        task_input = task_workdir / "input.csv"
        shutil.copy2(table_path, task_input)
        task_output = task_workdir / "output.txt"

        task_str = self._build_task_string(example, task_input, task_output)
        ground_truth = self._build_ground_truth_text(example)

        return {
            "index": idx,
            "id": ex_id,
            "example": example,
            "task_str": task_str,
            "ground_truth": ground_truth,
            "task_output": task_output,
            "task_workdir": task_workdir,
        }

    # ─── assessment ─────────────────────────────────────────────────────

    def assess(
        self, seed_data: dict, exec_result: dict, round_num: int = 0,
    ) -> dict:
        idx = seed_data["index"]
        ex_id = seed_data["id"]
        example = seed_data["example"]
        task_output: Path = seed_data["task_output"]

        target_strings: list[str] = example["answer_values"]
        predicted_strings = self._read_predicted(task_output)

        cell_comp = format_comparison(target_strings, predicted_strings)
        acc = compute_accuracy(target_strings, predicted_strings)
        is_correct = acc["accuracy"] == 1.0

        print(
            f"  [assess] Seed {idx} (id={ex_id}): "
            f"acc={acc['match_count']}/{acc['total_count']} "
            f"({acc['accuracy']:.1%}){' PASS' if is_correct else ''}"
        )

        # Per-round trace + assessment files
        trace_path = (
            Path(exec_result["task_workdir"]) / f"execution_trace_r{round_num}.md"
        )
        try:
            trace_text = build_execution_trace(exec_result["trajectory_path"])
            _write_workspace(trace_path, trace_text)
        except Exception as e:
            print(f"  [assess] Seed {idx}: trace extraction failed: {e}")
            _write_workspace(trace_path, "(trace extraction failed)")

        assessment_path = (
            Path(exec_result["task_workdir"]) / f"assessment_r{round_num}.json"
        )
        _write_workspace(assessment_path, {
            "accuracy": acc["accuracy"],
            "match_count": acc["match_count"],
            "total_count": acc["total_count"],
            "is_correct": is_correct,
            "predicted": predicted_strings,
            "target": target_strings,
        })

        return {
            "index": idx,
            "id": ex_id,
            "example": example,
            "task_str": seed_data["task_str"],
            "ground_truth": seed_data["ground_truth"],
            "executor_output": exec_result["executor_output"],
            "is_correct": is_correct,
            "accuracy": acc,
            "cell_comparison": cell_comp,
            "elapsed": exec_result["elapsed"],
            "trajectory_path": exec_result["trajectory_path"],
            "execution_trace_path": str(trace_path),
            "logger": exec_result["logger"],
            "task_workdir": exec_result["task_workdir"],
        }

    # ─── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _read_predicted(output_path: Path) -> list[str]:
        """Read executor-written ``output.txt`` as a list of answer strings.

        Empty file or missing file → empty list (will score 0 accuracy
        against any non-empty target).
        """
        if not output_path.exists():
            return []
        try:
            text = output_path.read_text(encoding="utf-8")
        except Exception:
            return []
        # One answer per non-blank line; strip trailing whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines

    @staticmethod
    def _build_task_string(
        example: dict, input_csv_path: Path, output_txt_path: Path,
    ) -> str:
        return (
            f"A user is asking a question about a table.\n\n"
            f"## User's Question\n"
            f"{example['instruction']}\n\n"
            f"## Input Table\n"
            f"The table is at: {input_csv_path}\n"
            f"It is a CSV file with a header row.\n\n"
            f"## Instructions\n"
            f"1. Read the input CSV table\n"
            f"2. Answer the user's question by computing in Python\n"
            f"3. Write the answer(s) to: {output_txt_path}\n"
            f"   - One answer per line.\n"
            f"   - Multi-answer questions: emit each answer on its own line.\n"
            f"   - Do not wrap answers in quotes; do not add units; emit "
            f"the literal value as it appears in the table.\n"
        )

    @staticmethod
    def _build_ground_truth_text(example: dict) -> str:
        targets = example["answer_values"]
        if len(targets) == 1:
            return f"Expected answer: {targets[0]}"
        return (
            f"Expected answers ({len(targets)} values):\n"
            + "\n".join(f"  - {v}" for v in targets)
        )


# ─── factory ────────────────────────────────────────────────────────────

def make_bench(data_dir, **kwargs) -> WTQBench:
    return WTQBench(data_dir=Path(data_dir).resolve())
