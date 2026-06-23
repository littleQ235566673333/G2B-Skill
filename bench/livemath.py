"""LiveMathBench adapter — Bench protocol implementation.

Mirrors bench/wtq.py shape so the rest of the pipeline treats LiveMath
uniformly. Differences from WTQ:

  - input is a single ``question.txt`` (the problem statement)
  - assess() routes through a LLM judge for math-equivalence rather than
    string match (see evaluators/livemath_compare.py)

On-disk layout expected at ``data_dir`` (built by
``data/benchmarks/build_livemath_dataset.py``)::

    data_dir/
    ├── dataset.json                    # list of {id, instruction, question_txt, answer, ...}
    └── question/
        └── <id>.txt                    # the problem statement (UTF-8)

dataset.json entry shape::

    {
      "id":            "lm-AMC-0",
      "instruction":   "Find the smallest positive integer n such that ...",
      "question_txt":  "question/lm-AMC-0.txt",
      "answer":        "12",
      "answer_values": ["12"],
      "source":        "AMC",
      "language":      "en",
      "question_type": "Problem-Solving"
    }

Per-task workspace
------------------
Each task gets ``task_workdir/evolve_<id>/``::

    question.txt   # copy of the problem statement
    output.txt     # the executor writes its final answer here

The seed at ``seeds/livemath/SKILL.md`` instructs the executor to write a
final \\boxed{...} or plain expression to ``output.txt``; assess() reads
it back, runs the LLM judge, and scores 1.0 / 0.0.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from evaluators.livemath_compare import compute_accuracy, format_comparison
from pipeline.execution import _write_workspace
from runners.trajectory_logger import build_execution_trace


@dataclass
class LiveMathBench:
    """LiveMathBench bench (Olympiad / AMC / Putnam style)."""

    data_dir: Path
    name: str = "livemath"
    skill_name: str = "livemath"

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

        q_path = self.data_dir / example["question_txt"]
        if not q_path.exists():
            raise FileNotFoundError(
                f"LiveMath question not found: {q_path} "
                f"(referenced by example {ex_id!r})"
            )

        task_workdir = workdir / (task_dir_name or f"evolve_{ex_id}")
        task_workdir.mkdir(parents=True, exist_ok=True)
        task_input = task_workdir / "question.txt"
        shutil.copy2(q_path, task_input)
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

        # Pass through the question text so the judge has problem context.
        cell_comp = format_comparison(
            target_strings, predicted_strings, question=example["instruction"],
        )
        acc = compute_accuracy(
            target_strings, predicted_strings,
            question=example["instruction"],
        )
        is_correct = acc["accuracy"] == 1.0

        print(
            f"  [assess] Seed {idx} (id={ex_id}): "
            f"verdict={acc['judge_verdict']}"
            f"{' PASS' if is_correct else ''}"
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
            "judge_verdict": acc["judge_verdict"],
            "judge_reasoning": acc["judge_reasoning"],
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
        if not output_path.exists():
            return []
        try:
            text = output_path.read_text(encoding="utf-8")
        except Exception:
            return []
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines

    @staticmethod
    def _build_task_string(
        example: dict, question_path: Path, output_path: Path,
    ) -> str:
        return (
            f"You are given a math problem. Reason step by step in Python "
            f"or symbolically, then write your final answer to a file.\n\n"
            f"## Problem (source: {example.get('source', 'unknown')})\n"
            f"{example['instruction']}\n\n"
            f"## Problem file\n"
            f"The full statement is also available at: {question_path}\n\n"
            f"## Instructions\n"
            f"1. Reason about the problem. You may use Python (sympy, "
            f"numpy, math) for symbolic / numeric work.\n"
            f"2. Write the FINAL answer to: {output_path}\n"
            f"   - One line, the literal final answer expression.\n"
            f"   - Use \\boxed{{...}} around the answer if helpful (the "
            f"evaluator strips it).\n"
            f"   - For multi-part / multi-value answers (sets, tuples), "
            f"write a single canonical form (e.g. 'x = 1 or x = 2', "
            f"or '(0, 1/2)').\n"
            f"   - The answer is judged via mathematical equivalence — "
            f"don't worry about LaTeX vs ASCII, but DO worry about getting "
            f"all required values.\n"
        )

    @staticmethod
    def _build_ground_truth_text(example: dict) -> str:
        return f"Expected answer: {example.get('answer', '')}"


# ─── factory ────────────────────────────────────────────────────────────

def make_bench(data_dir, **kwargs) -> LiveMathBench:
    return LiveMathBench(data_dir=Path(data_dir).resolve())
