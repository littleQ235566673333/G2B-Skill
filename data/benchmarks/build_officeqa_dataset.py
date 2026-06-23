"""Build a SkillGrad-compatible dataset.json from the OfficeQA HF release.

Source: ``databricks/officeqa`` (gated on HF). The ``Pro`` config (N=133)
is the frontier-model split everyone reports; ``Full`` (N=246) is the
unfiltered superset.

Per Databricks tech report, OfficeQA is grounded reasoning QA over
**U.S. Treasury Bulletin** documents (1939–2025). Each task references
a small set of source documents — the agent must read them and produce
the answer. Despite the name, OfficeQA is NOT Microsoft-Office automation;
"Office" refers to the U.S. Treasury (federal office). All source files
are plain text (parsed from PDFs by Databricks).

Output layout (mirrors WTQ / SearchQA shape)::

    data/benchmarks/officeqa/
    ├── dataset.json                     # list of {id, instruction, sources_dir, answer, ...}
    ├── corpus/                          # parsed Treasury Bulletin .txt corpus (full or task-relevant subset)
    │   └── ...
    └── per_task_sources/
        └── <id>/                        # symlinks to the source_files referenced by this task
            └── ...

dataset.json entry shape::

    {
      "id":            "oqa-0",
      "instruction":   "What was ...",
      "sources_dir":   "per_task_sources/oqa-0",
      "answer":        "12345.67",
      "answer_values": ["12345.67"],
      "tolerance_pct": 1.0,
      "source_files":  ["bulletin_1942_q1.txt", "bulletin_1942_q2.txt"]
    }

Build process
-------------
1. Download the CSV (officeqa_pro.csv by default) and parse rows.
2. Snapshot-download the parsed-text corpus (allow_patterns
   ``treasury_bulletins_parsed/transformed/*.txt``, ~460MB).
3. For each task, materialize a ``per_task_sources/<id>/`` directory of
   symlinks pointing into the corpus — keeps per-task copy cost zero
   while making the bench's ``prepare_seed_data`` filesystem-local.

Run once::

    .venv/bin/python -m data.benchmarks.build_officeqa_dataset --split pro
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

HF_ID = "databricks/officeqa"


def _download_csv(hf_id: str, hf_token: str | None,
                  csv_name: str, out_dir: Path) -> Path:
    """Download one CSV from the HF repo. Returns the local path."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        sys.exit(
            "huggingface_hub package not installed. "
            "Install with: .venv/bin/pip install huggingface_hub"
        )

    print(f"[officeqa] downloading {csv_name} from {hf_id} ...")
    local_path = hf_hub_download(
        repo_id=hf_id,
        filename=csv_name,
        repo_type="dataset",
        token=hf_token,
        cache_dir=str(out_dir / "_hf_cache"),
    )
    return Path(local_path)


def _snapshot_corpus(hf_id: str, hf_token: str | None, out_dir: Path) -> Path:
    """Snapshot-download the parsed-text corpus only (skip PDFs)."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        sys.exit(
            "huggingface_hub package not installed. "
            "Install with: .venv/bin/pip install huggingface_hub"
        )

    print(f"[officeqa] downloading text corpus (~460MB) ...")
    local_root = snapshot_download(
        repo_id=hf_id,
        repo_type="dataset",
        token=hf_token,
        cache_dir=str(out_dir / "_hf_cache"),
        allow_patterns=["treasury_bulletins_parsed/transformed/*.txt"],
    )
    return Path(local_root)


def _parse_csv(path: Path) -> list[dict]:
    """Parse the OfficeQA CSV and return a list of raw row dicts.

    Schema (per Databricks tech report):
        uid, question, answer, source_docs, source_files

    ``source_files`` is a JSON list of relative paths into the parsed
    corpus; ``source_docs`` is a human-readable description of the same.
    """
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def _parse_source_files_field(s: str) -> list[str]:
    """``source_files`` may be: JSON list, newline-separated, pipe-separated,
    or comma-separated. Be lenient — try newlines first since that's what
    the OfficeQA Pro CSV actually uses."""
    s = (s or "").strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            arr = json.loads(s)
            return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
    # Newline first (OfficeQA Pro CSV convention)
    if "\n" in s:
        return [x.strip() for x in s.splitlines() if x.strip()]
    if "|" in s:
        return [x.strip() for x in s.split("|") if x.strip()]
    if "," in s:
        return [x.strip() for x in s.split(",") if x.strip()]
    return [s]


def _to_skillgrad_entry(row: dict, slot: int, default_tol_pct: float) -> dict:
    uid = row.get("uid") or row.get("id") or f"oqa-{slot}"
    src_files = _parse_source_files_field(row.get("source_files", ""))
    return {
        "id":            f"oqa-{slot}",
        "uid_orig":      uid,
        "instruction":   row.get("question", ""),
        "sources_dir":   f"per_task_sources/oqa-{slot}",
        "answer":        row.get("answer", ""),
        "answer_values": [row.get("answer", "")],
        "tolerance_pct": default_tol_pct,
        "source_files":  src_files,
    }


def _resolve_corpus_path(corpus_root: Path, rel: str) -> Path | None:
    """Find a source file inside the corpus snapshot.

    The CSV's ``source_files`` may use different prefixes than the on-disk
    layout. Try a few candidate prefixes; return the first that exists.
    """
    rel = rel.strip().lstrip("./")
    candidates = [
        corpus_root / rel,
        corpus_root / "treasury_bulletins_parsed" / "transformed" / rel,
        corpus_root / "treasury_bulletins_parsed" / rel,
    ]
    # If rel doesn't end in .txt, try .txt variant
    if not rel.endswith(".txt"):
        candidates.append(corpus_root / "treasury_bulletins_parsed" / "transformed" / f"{rel}.txt")
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf-id", default=HF_ID)
    ap.add_argument("--split", choices=["pro", "full"], default="pro",
                    help="pro=133 frontier; full=246 superset.")
    ap.add_argument("--output", default="data/benchmarks/officeqa")
    ap.add_argument("--default-tolerance-pct", type=float, default=1.0,
                    help="Per-task fuzzy-numerical tolerance percent. "
                         "OfficeQA reports 0/0.1/1/5% — 1%% is the "
                         "common reporting tolerance.")
    args = ap.parse_args()

    output = Path(args.output).resolve()
    hf_token = os.environ.get("HF_TOKEN")
    output.mkdir(parents=True, exist_ok=True)

    csv_name = f"officeqa_{args.split}.csv"
    csv_path = _download_csv(args.hf_id, hf_token, csv_name, output)
    rows = _parse_csv(csv_path)
    print(f"[officeqa] parsed {len(rows)} rows from {csv_name}")
    if rows:
        print(f"[officeqa] CSV columns: {list(rows[0].keys())}")

    corpus_root = _snapshot_corpus(args.hf_id, hf_token, output)
    print(f"[officeqa] corpus root: {corpus_root}")

    per_task_dir = output / "per_task_sources"
    per_task_dir.mkdir(exist_ok=True)

    entries: list[dict] = []
    missing_total = 0
    for slot, row in enumerate(rows):
        entry = _to_skillgrad_entry(row, slot, args.default_tolerance_pct)
        # Materialize per-task source dir
        task_src_dir = output / entry["sources_dir"]
        task_src_dir.mkdir(parents=True, exist_ok=True)
        resolved: list[str] = []
        missing: list[str] = []
        for rel in entry["source_files"]:
            resolved_path = _resolve_corpus_path(corpus_root, rel)
            if resolved_path is None:
                missing.append(rel)
                continue
            link = task_src_dir / Path(rel).name
            if not link.exists():
                try:
                    link.symlink_to(resolved_path.resolve())
                except FileExistsError:
                    pass
            resolved.append(link.name)
        entry["source_files_resolved"] = resolved
        entry["source_files_missing"] = missing
        if missing:
            missing_total += len(missing)
        entries.append(entry)

    out_json = output / "dataset.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"[officeqa] wrote {len(entries)} entries -> {out_json}")
    if missing_total:
        print(f"[officeqa] WARNING: {missing_total} source files unresolved; "
              f"check corpus prefix logic in _resolve_corpus_path()")
    if entries:
        print(f"[officeqa] sample entry:\n{json.dumps(entries[0], ensure_ascii=False, indent=2)[:600]}")


if __name__ == "__main__":
    main()
