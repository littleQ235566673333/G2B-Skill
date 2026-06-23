"""SpreadsheetBench adapter — SkillGrad's native bench, wrapped in Bench protocol.

Wraps the dataset I/O, per-task workdir setup, task-string construction,
and assessment that previously lived as top-level functions in
``pipeline/execution.py``. Behavior is preserved exactly so SkillGrad
runs through this adapter reproduce the same numbers as the original
pipeline.

On-disk layout expected at ``data_dir``::

    data_dir/
    ├── dataset.json
    └── spreadsheet/
        ├── <id>/
        │   ├── 1_<id>_input.xlsx     # input workbook
        │   ├── 1_<id>_answer.xlsx    # reference answer
        │   └── ...
        └── ...

The bundled SpreadsheetBench Verified release follows this layout; see
``data/benchmarks/README.md`` for the three accepted naming conventions
(``data/load.py`` already handles all of them).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from evaluators.xlsx_compare import (
    cells_to_text,
    compute_accuracy,
    extract_cells,
    format_comparison,
)
from pipeline.execution import _write_workspace
from runners.trajectory_logger import build_execution_trace


@dataclass
class SpreadsheetBench:
    """SpreadsheetBench Verified bench (SkillGrad's native bench)."""

    data_dir: Path
    name: str = "spreadsheet"
    skill_name: str = "xlsx"

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

        spreadsheet_dir = self.data_dir / "spreadsheet" / str(ex_id)
        input_path = spreadsheet_dir / f"1_{ex_id}_input.xlsx"
        answer_path = spreadsheet_dir / f"1_{ex_id}_answer.xlsx"

        task_workdir = workdir / (task_dir_name or f"evolve_{ex_id}")
        task_workdir.mkdir(parents=True, exist_ok=True)
        task_input = task_workdir / "input.xlsx"
        shutil.copy2(input_path, task_input)
        task_output = task_workdir / "output.xlsx"

        task_str = self._build_task_string(example, task_input, task_output)
        ground_truth = self._build_ground_truth_text(example, answer_path)

        return {
            "index": idx,
            "id": ex_id,
            "example": example,
            "task_str": task_str,
            "ground_truth": ground_truth,
            "task_output": task_output,
            "answer_path": answer_path,
            "task_workdir": task_workdir,
        }

    # ─── assessment ─────────────────────────────────────────────────────

    def assess(
        self, seed_data: dict, exec_result: dict, round_num: int = 0,
    ) -> dict:
        idx = seed_data["index"]
        ex_id = seed_data["id"]
        example = seed_data["example"]
        task_output = seed_data["task_output"]
        answer_path = seed_data["answer_path"]

        # format_comparison recalculates the output file (soffice) once,
        # then compute_accuracy skips recalculation to avoid double work.
        cell_comp = format_comparison(
            task_output, answer_path, example["answer_position"],
        )
        acc = compute_accuracy(
            task_output, answer_path, example["answer_position"],
            recalculate=False,
        )
        is_correct = acc["accuracy"] == 1.0

        print(
            f"  [assess] Seed {idx} (id={ex_id}): "
            f"acc={acc['match_count']}/{acc['total_count']} "
            f"({acc['accuracy']:.1%}){' PASS' if is_correct else ''}"
        )

        # Per-round trace + assessment files (no overwrites across rounds)
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

    # ─── task-string + ground-truth helpers ─────────────────────────────

    @staticmethod
    def _build_task_string(
        example: dict, input_xlsx_path: Path, output_xlsx_path: Path,
    ) -> str:
        return (
            f"A user needs help with a spreadsheet task.\n\n"
            f"## User's Request\n"
            f"{example['instruction']}\n\n"
            f"## Input File\n"
            f"The spreadsheet is at: {input_xlsx_path}\n\n"
            f"## Instructions\n"
            f"1. Read the input spreadsheet\n"
            f"2. Write Python code to accomplish the user's request\n"
            f"3. Save the result to: {output_xlsx_path}\n"
            f"4. The answer should appear in cells: {example['answer_position']}\n\n"
            f"Use openpyxl to read and write the Excel file. "
            f"Make sure to save the workbook after making changes."
        )

    @staticmethod
    def _build_ground_truth_text(example: dict, answer_xlsx_path: Path) -> str:
        cells = extract_cells(answer_xlsx_path, example["answer_position"])
        return (
            f"Expected cell values at {example['answer_position']}:\n"
            + cells_to_text(cells)
        )


# ─── factory ────────────────────────────────────────────────────────────

def make_bench(data_dir, **kwargs) -> SpreadsheetBench:
    return SpreadsheetBench(data_dir=Path(data_dir).resolve())
