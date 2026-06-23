"""Build a SkillGrad-compatible dataset.json from the SearchQA HF release.

Source: ``lucadiliello/searchqa`` on HuggingFace (MRQA-2019 reformat — the
snippets-given variant: each example has a single ``context`` string with
~50 snippets concatenated via [DOC]/[TLE]/[PAR] markers).

Output layout (mirrors WTQ shape)::

    data/benchmarks/searchqa/
    ├── dataset.json                  # list of {id, instruction, context_txt, answer_values}
    └── context/
        └── <id>.txt                  # the snippets-bundle for each example

Each ``id`` maps to one Q/A; ``context_txt`` is RELATIVE to dataset.json's dir;
``answer_values`` is a list of accepted gold strings (typically length 1).

Bench budget alignment: we mirror SpreadsheetBench Verified's 400-task pool
by emitting the first 400 deterministically-shuffled examples of the
validation split (16,980 total). That gives plenty of headroom for the
40-train / 100-test (master_seed=0) split the rest of the pipeline assumes.

Run once::

    .venv/bin/python -m data.benchmarks.build_searchqa_dataset
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path


def _load_hf_validation(hf_id: str, hf_token: str | None) -> list[dict]:
    """Load the validation split from HuggingFace.

    Returns a list of raw HF rows (dicts with keys: question, context, answers, ...).
    """
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit(
            "datasets package not installed. "
            "Install with: .venv/bin/pip install datasets"
        )

    print(f"[searchqa] loading {hf_id} validation from HF...")
    kwargs = {"split": "validation"}
    if hf_token:
        kwargs["token"] = hf_token
    ds = load_dataset(hf_id, **kwargs)
    rows = list(ds)
    print(f"[searchqa] loaded {len(rows)} validation rows")
    return rows


def _to_skillgrad_entry(row: dict, idx: int) -> dict:
    """Convert one HF row to a SkillGrad-compatible dataset entry.

    HF row schema (lucadiliello/searchqa):
        {
          "key": "<md5-hex>",
          "question": "<q>",
          "context":  "[DOC] [TLE] ... [PAR] ...",
          "answers":  ["<gold>", ...],
          "labels":   [{"start": [...], "end": [...]}],
        }
    """
    ex_id = f"sq-{idx}"  # short stable id keyed by deterministic shuffle index
    return {
        "id":            ex_id,
        "hf_key":        row.get("key", ""),
        "instruction":   row["question"],
        "context_txt":   f"context/{ex_id}.txt",
        "answer_values": list(row["answers"]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--hf-id", default="lucadiliello/searchqa",
        help="HuggingFace dataset id (default: lucadiliello/searchqa)",
    )
    ap.add_argument(
        "--output", default="data/benchmarks/searchqa",
        help="Output directory for the SkillGrad-compatible layout.",
    )
    ap.add_argument(
        "--n-tasks", type=int, default=400,
        help="Number of tasks to emit. Matches SS/WTQ pool size.",
    )
    ap.add_argument(
        "--shuffle-seed", type=int, default=0,
        help="Deterministic shuffle seed before truncation.",
    )
    args = ap.parse_args()

    output = Path(args.output).resolve()
    hf_token = os.environ.get("HF_TOKEN")

    rows = _load_hf_validation(args.hf_id, hf_token)

    # Deterministic shuffle then take first n_tasks
    rng = random.Random(args.shuffle_seed)
    indices = list(range(len(rows)))
    rng.shuffle(indices)
    if args.n_tasks > 0:
        indices = indices[: args.n_tasks]

    output.mkdir(parents=True, exist_ok=True)
    context_dir = output / "context"
    context_dir.mkdir(exist_ok=True)

    entries: list[dict] = []
    for slot, src_idx in enumerate(indices):
        row = rows[src_idx]
        entry = _to_skillgrad_entry(row, slot)
        entries.append(entry)
        # Write the context bundle to disk
        ctx_path = output / entry["context_txt"]
        ctx_path.write_text(row["context"], encoding="utf-8")

    out_json = output / "dataset.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"[searchqa] wrote {len(entries)} entries -> {out_json}")
    print(f"[searchqa] context files in {context_dir}")
    print(f"[searchqa] sample entry:\n{json.dumps(entries[0], ensure_ascii=False, indent=2)[:500]}")


if __name__ == "__main__":
    main()
