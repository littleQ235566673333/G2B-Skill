"""Bench abstraction for SkillGrad-style pipelines.

A Bench owns:
  - on-disk dataset layout (load_dataset)
  - per-task workspace setup (prepare_seed_data)
  - task-string + ground-truth construction handed to the executor
  - assessment of executor output (cell-comparison or string match)

This is the only bench-specific surface the rest of the pipeline sees.
``pipeline/execution.py:run_execute``, ``pipeline/diagnoser.py``,
``pipeline/training.py`` are all bench-agnostic and operate via a Bench
instance threaded through their args.

Usage::

    from bench import get_bench
    bench = get_bench("spreadsheet", data_dir="data/benchmarks/spreadsheetbench")
    dataset = bench.load_dataset()
    seed_data = bench.prepare_seed_data(dataset, idx=0, workdir=Path("results/run/iter_1"))
    # ... run_execute(seed_data, ...) ...
    assessment = bench.assess(seed_data, exec_result, round_num=0)

Adding a new bench
------------------
1. Create ``bench/<name>.py`` with a class implementing Bench + a
   ``make_bench(**kwargs) -> Bench`` factory.
2. Add an ``elif name == "<name>":`` branch to ``get_bench()`` below
   (lazy imports keep deps isolated per bench).
3. Add a seed skill at ``seeds/<skill_name>/SKILL.md`` referenced by
   ``bench.skill_name``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Bench(Protocol):
    """Bench-specific data + assessment surface.

    Identifiers
    -----------
    name        : canonical short name; used in path layout
                  (e.g. ``"spreadsheet"``, ``"wtq"``).
    skill_name  : the skill to activate in the executor
                  (e.g. ``"xlsx"`` for SpreadsheetBench, ``"wtq"`` for WTQ).
    """

    name: str
    skill_name: str

    def load_dataset(self) -> list[dict]:
        """Load the full dataset as a list of example dicts.

        Each example dict must contain at minimum:
          - ``"id"``: unique task id (str-coercible)
        Other keys are bench-specific and only the bench's own
        ``prepare_seed_data`` and ``assess`` should rely on them.
        """
        ...

    def prepare_seed_data(
        self, dataset: list[dict], idx: int, workdir: Path,
        task_dir_name: str | None = None,
    ) -> dict:
        """Set up per-task working directory and return a seed_data dict.

        ``task_dir_name`` overrides the per-task subdir name under
        ``workdir``. When ``None`` (default), bench uses
        ``f"evolve_{example['id']}"`` (the SkillGrad-native naming).

        seed_data must contain at minimum:
          - ``index``, ``id``, ``example``
          - ``task_str``: full prompt text handed to the executor
          - ``ground_truth``: text reference for diagnoser context
          - ``task_workdir``: per-task scratch directory
        Bench-specific extras (input_path, answer_path, ...) are allowed
        but only the bench's own ``assess`` method should rely on them.
        """
        ...

    def assess(
        self, seed_data: dict, exec_result: dict, round_num: int = 0,
    ) -> dict:
        """Programmatically score the executor's output for this seed.

        Returns an assessment dict with at minimum:
          - ``id``, ``example``, ``task_str``, ``ground_truth``
          - ``is_correct`` (bool)
          - ``accuracy``: dict with ``accuracy``, ``match_count``, ``total_count``
          - ``cell_comparison`` (str): bench-specific human-readable diff
          - ``executor_output``, ``elapsed``, ``trajectory_path``
          - ``execution_trace_path``, ``logger``, ``task_workdir``
        Compatible with downstream diagnoser / momentum / patcher.
        """
        ...


# ─── factory ────────────────────────────────────────────────────────────

def get_bench(name: str, **kwargs) -> Bench:
    """Look up a Bench implementation by canonical name.

    Lazy imports — adding a new bench doesn't drag its deps into every
    other code path.
    """
    if name == "spreadsheet":
        from bench.spreadsheetbench import make_bench
        return make_bench(**kwargs)
    if name == "wtq":
        from bench.wtq import make_bench
        return make_bench(**kwargs)
    if name == "searchqa":
        from bench.searchqa import make_bench
        return make_bench(**kwargs)
    if name == "livemath":
        from bench.livemath import make_bench
        return make_bench(**kwargs)
    if name == "officeqa":
        from bench.officeqa import make_bench
        return make_bench(**kwargs)
    raise ValueError(
        f"unknown bench {name!r}; known: spreadsheet, wtq, searchqa, livemath, officeqa"
    )


__all__ = ["Bench", "get_bench"]
