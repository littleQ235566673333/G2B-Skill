"""Build a SkillGrad-compatible dataset.json from the WikiTableQuestions release.

Source layout (from the GitHub release tarball, extracted at
``data/benchmarks/wikitablequestions_raw/WikiTableQuestions-master/``)::

    data/training.tsv                       # 14152 rows: id, utterance, context, targetValue
    data/pristine-unseen-tables.tsv         # 4344 rows: canonical leaderboard test
    csv/<XXX>-csv/<NNN>.csv                 # tables

Output layout (SkillGrad-style, at ``data/benchmarks/wikitablequestions/``)::

    dataset.json                            # list of {id, instruction, table_csv, answer_values}
    csv/                                    # symlink to ../wikitablequestions_raw/.../csv

Each entry ``id`` maps to one question; ``table_csv`` is RELATIVE to the
dataset.json directory; ``answer_values`` is a list (multi-answer rows
in WTQ are pipe-separated).

Bench budget alignment: we mirror SpreadsheetBench Verified's 400-task
pool by emitting the first 400 rows of ``training.tsv``. The canonical
``pristine-unseen-tables.tsv`` is reserved for an optional final
leaderboard number; not used for our evolve/held-out split.

Run once::

    python -m data.benchmarks.build_wtq_dataset
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def _parse_tsv_rows(path: Path) -> list[dict]:
    """Parse a WTQ TSV file. Header: id, utterance, context, targetValue."""
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            rows.append({
                "id":           r["id"],
                "utterance":    r["utterance"],
                "context":      r["context"],
                "targetValue":  r["targetValue"],
            })
    return rows


def _to_skillgrad_entry(row: dict) -> dict:
    """Convert a WTQ TSV row to a SkillGrad-compatible dataset entry.

    Multi-answer rows in WTQ encode answers separated by ``|``; we keep
    the full list. The Stanford evaluator is set-equality-based so order
    is irrelevant.
    """
    return {
        "id":            row["id"],
        "instruction":   row["utterance"],
        "table_csv":     row["context"],          # relative to dataset.json's dir
        "answer_values": row["targetValue"].split("|"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--source",
        default="data/benchmarks/wikitablequestions_raw/WikiTableQuestions-master",
        help="Path to extracted WTQ master directory.",
    )
    ap.add_argument(
        "--output",
        default="data/benchmarks/wikitablequestions",
        help="Output directory for the SkillGrad-compatible layout.",
    )
    ap.add_argument(
        "--split-tsv",
        default="data/training.tsv",
        help="Which TSV inside the source dir to sample from.",
    )
    ap.add_argument(
        "--n-tasks",
        type=int,
        default=400,
        help=("Number of tasks to emit. Mirrors SpreadsheetBench Verified's "
              "400-task pool. Pass 0 to emit all rows."),
    )
    args = ap.parse_args()

    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    split_path = source / args.split_tsv

    if not split_path.exists():
        sys.exit(f"split TSV not found: {split_path}")
    if not (source / "csv").exists():
        sys.exit(f"csv/ dir not found under source: {source / 'csv'}")

    rows = _parse_tsv_rows(split_path)
    print(f"Loaded {len(rows)} rows from {split_path.relative_to(source)}")

    if args.n_tasks > 0:
        rows = rows[: args.n_tasks]
        print(f"Truncated to first {len(rows)} rows")

    entries = [_to_skillgrad_entry(r) for r in rows]

    # Materialize output dir + symlink the csv tables
    output.mkdir(parents=True, exist_ok=True)
    csv_link = output / "csv"
    if not csv_link.exists():
        csv_link.symlink_to(source / "csv")
        print(f"Symlinked {csv_link} -> {source / 'csv'}")

    # Verify every table referenced by an entry actually exists
    missing = []
    for e in entries:
        if not (output / e["table_csv"]).exists():
            missing.append(e["id"])
    if missing:
        print(f"WARNING: {len(missing)} entries reference missing CSVs "
              f"(first 5: {missing[:5]})")

    out_json = output / "dataset.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(entries)} entries -> {out_json}")
    print(f"Sample entry:\n{json.dumps(entries[0], ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
