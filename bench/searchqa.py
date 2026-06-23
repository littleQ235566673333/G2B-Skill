"""SearchQA adapter — Bench protocol implementation.

Mirrors bench/wtq.py's shape so the rest of the pipeline (run_execute,
training loop, diagnoser, momentum, patcher) treats SearchQA uniformly.

On-disk layout expected at ``data_dir`` (built by
``data/benchmarks/build_searchqa_dataset.py``)::

    data_dir/
    ├── dataset.json         # list of {id, instruction, context_txt, answer_values}
    └── context/
        └── <id>.txt         # the snippets-bundle for each example

dataset.json entry shape::

    {
      "id":            "sq-0",
      "instruction":   "1976: \"A Single Colorado Mountain\"",
      "context_txt":   "context/sq-0.txt",
      "answer_values": ["Rocky"]
    }

Per-task workspace
------------------
Each task gets ``task_workdir/evolve_<id>/``::

    input.txt     # copy of context bundle (~50 search snippets w/ DOC/TLE/PAR markers)
    output.txt    # the executor writes its single short answer here

The seed skill at ``seeds/searchqa/SKILL.md`` instructs the executor to
write to ``output.txt``; assess() reads it back and scores via SQuAD-style
EM + F1.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from evaluators.searchqa_compare import compute_accuracy, format_comparison
from pipeline.execution import _write_workspace
from runners.trajectory_logger import build_execution_trace


@dataclass
class SearchQABench:
    """SearchQA bench (snippets-given QA, MRQA-2019 reformat)."""

    data_dir: Path
    name: str = "searchqa"
    skill_name: str = "searchqa"

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

        ctx_path = self.data_dir / example["context_txt"]
        if not ctx_path.exists():
            raise FileNotFoundError(
                f"SearchQA context not found: {ctx_path} "
                f"(referenced by example {ex_id!r})"
            )

        task_workdir = workdir / (task_dir_name or f"evolve_{ex_id}")
        task_workdir.mkdir(parents=True, exist_ok=True)
        task_input = task_workdir / "input.txt"
        shutil.copy2(ctx_path, task_input)
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
            f"EM={acc['em']:.0f} F1={acc['f1']:.2f}"
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
            "em": acc["em"],
            "f1": acc["f1"],
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
        example: dict, input_txt_path: Path, output_txt_path: Path,
    ) -> str:
        return (
            f"You are given a question and a bundle of search-result snippets. "
            f"Read the snippets and produce the short answer to the question.\n\n"
            f"## Question\n"
            f"{example['instruction']}\n\n"
            f"## Snippets file\n"
            f"The search snippets bundle is at: {input_txt_path}\n"
            f"Snippets are concatenated; each one starts with a [DOC] [TLE] "
            f"<title> [PAR] header followed by paragraph text.\n\n"
            f"## Instructions\n"
            f"1. Read the snippets file in Python (it's plain UTF-8 text).\n"
            f"2. Extract the short answer (typically a single named entity or "
            f"phrase) implied by the snippets.\n"
            f"3. Write that answer to: {output_txt_path}\n"
            f"   - One line, the literal answer string.\n"
            f"   - Do NOT add explanations, units, articles (a/an/the are stripped "
            f"in normalization but cleaner is better), or quotes.\n"
            f"   - Match how the answer would appear in plain text.\n"
        )

    @staticmethod
    def _build_ground_truth_text(example: dict) -> str:
        targets = example["answer_values"]
        if len(targets) == 1:
            return f"Expected answer: {targets[0]}"
        return (
            f"Expected answer (any acceptable, {len(targets)} variants):\n"
            + "\n".join(f"  - {v}" for v in targets)
        )


# ─── factory ────────────────────────────────────────────────────────────

def make_bench(data_dir, **kwargs) -> SearchQABench:
    return SearchQABench(data_dir=Path(data_dir).resolve())
