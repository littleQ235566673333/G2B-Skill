"""OfficeQA adapter — Bench protocol implementation.

OfficeQA is grounded reasoning QA over Treasury Bulletin documents
(databricks/officeqa). Despite the name, "Office" refers to the U.S.
Treasury (federal office), NOT Microsoft Office. Each task references
a small set of source documents (parsed text files); the agent reads
them and produces a single short answer (often a number).

On-disk layout expected at ``data_dir`` (built by
``data/benchmarks/build_officeqa_dataset.py``)::

    data_dir/
    ├── dataset.json                    # list of {id, instruction, sources_dir, answer, ...}
    └── per_task_sources/
        └── <id>/                       # symlinks into the parsed Treasury corpus
            └── <doc>.txt

dataset.json entry shape::

    {
      "id":            "oqa-0",
      "instruction":   "What was the total federal debt at the end of FY 1942?",
      "sources_dir":   "per_task_sources/oqa-0",
      "answer":        "72_422_000_000",
      "answer_values": ["72_422_000_000"],
      "tolerance_pct": 1.0,
      "source_files":  ["bulletin_1942_q4_p17.txt", ...]
    }

Per-task workspace
------------------
Each task gets ``task_workdir/evolve_<id>/``::

    sources/                   # symlink directory pointing at per_task_sources/<id>/
    output.txt                 # the executor writes its single short answer here

The seed at ``seeds/officeqa/SKILL.md`` instructs the executor to scan
the source files (which can be large) for the answer, then write it to
``output.txt``. assess() reads output.txt and scores via fuzzy numerical
match (relative error <= tolerance_pct).
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from evaluators.officeqa_compare import compute_accuracy, format_comparison
from pipeline.execution import _write_workspace
from runners.trajectory_logger import build_execution_trace


@dataclass
class OfficeQABench:
    """OfficeQA bench (Treasury Bulletin grounded reasoning QA)."""

    data_dir: Path
    name: str = "officeqa"
    skill_name: str = "officeqa"

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

        sources_src = self.data_dir / example["sources_dir"]
        if not sources_src.exists():
            raise FileNotFoundError(
                f"OfficeQA per-task sources dir not found: {sources_src} "
                f"(referenced by example {ex_id!r})"
            )

        task_workdir = workdir / (task_dir_name or f"evolve_{ex_id}")
        task_workdir.mkdir(parents=True, exist_ok=True)

        # Symlink the per-task sources dir into task_workdir/sources/.
        # The agent then reads files via Path("sources/...").read_text().
        task_sources = task_workdir / "sources"
        if task_sources.exists() or task_sources.is_symlink():
            try:
                if task_sources.is_symlink() or task_sources.is_file():
                    task_sources.unlink()
                else:
                    shutil.rmtree(task_sources)
            except Exception:
                pass
        try:
            task_sources.symlink_to(sources_src.resolve())
        except OSError:
            # Fallback: hard-copy when symlinks not supported (rare on local FS).
            shutil.copytree(sources_src, task_sources)

        task_output = task_workdir / "output.txt"

        task_str = self._build_task_string(example, task_sources, task_output)
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
        tol_pct = float(example.get("tolerance_pct", 1.0))

        cell_comp = format_comparison(
            target_strings, predicted_strings, tolerance_pct=tol_pct,
        )
        acc = compute_accuracy(
            target_strings, predicted_strings, tolerance_pct=tol_pct,
        )
        is_correct = acc["accuracy"] == 1.0

        match_type = acc.get("match_type", "?")
        if match_type == "numerical":
            print(
                f"  [assess] Seed {idx} (id={ex_id}): "
                f"rel_err={acc.get('rel_error', float('inf')):.4f} "
                f"@{tol_pct}%"
                f"{' PASS' if is_correct else ''}"
            )
        else:
            print(
                f"  [assess] Seed {idx} (id={ex_id}): "
                f"em={acc.get('em', 0):.0f} f1={acc.get('f1', 0):.2f}"
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
            "match_type": match_type,
            "tolerance_pct": tol_pct,
            "predicted": predicted_strings,
            "target": target_strings,
            "details": {k: v for k, v in acc.items()
                        if k not in ("accuracy", "match_count", "total_count")},
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
        example: dict, sources_path: Path, output_path: Path,
    ) -> str:
        # List source filenames so the agent knows what to look at.
        file_listing = ""
        try:
            files = sorted(p.name for p in sources_path.iterdir())
            if files:
                file_listing = (
                    "\n## Files in the sources directory\n"
                    + "\n".join(f"  - {f}" for f in files[:40])
                    + ("\n  ... (more)" if len(files) > 40 else "")
                )
        except Exception:
            pass

        return (
            f"You are answering a grounded reasoning question over U.S. "
            f"Treasury Bulletin documents.\n\n"
            f"## Question\n"
            f"{example['instruction']}\n\n"
            f"## Source documents\n"
            f"All relevant source documents are in the directory: {sources_path}\n"
            f"Each is a plain UTF-8 text file (parsed from the original PDF). "
            f"They contain dense financial tables and narrative text — read "
            f"selectively, search for the right keywords first.\n"
            f"{file_listing}\n\n"
            f"## Instructions\n"
            f"1. Identify which document(s) and section(s) answer the question.\n"
            f"2. Extract the answer (typically a dollar amount, count, or short phrase).\n"
            f"3. Write the answer to: {output_path}\n"
            f"   - One line, the numeric value (digits only — no $ sign, no "
            f"commas, no units in words). Or, for non-numeric answers, "
            f"the literal short phrase.\n"
            f"   - The grader accepts numerical matches within "
            f"{example.get('tolerance_pct', 1.0)}% relative error, so be "
            f"precise but small rounding is OK.\n"
            f"   - Do NOT add explanations, source citations, or context.\n"
        )

    @staticmethod
    def _build_ground_truth_text(example: dict) -> str:
        return (
            f"Expected answer: {example.get('answer', '')}\n"
            f"Tolerance: {example.get('tolerance_pct', 1.0)}% relative error "
            f"for numerical answers; exact match (after SQuAD normalization) "
            f"for non-numeric."
        )


# ─── factory ────────────────────────────────────────────────────────────

def make_bench(data_dir, **kwargs) -> OfficeQABench:
    return OfficeQABench(data_dir=Path(data_dir).resolve())
