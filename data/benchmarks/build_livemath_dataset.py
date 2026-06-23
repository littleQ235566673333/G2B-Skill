"""Build a SkillGrad-compatible dataset.json from LiveMathBench (gated HF release).

Source: ``opencompass/LiveMathBench`` v202412, English splits. The 4 source
configs (CNMO / CCEE / AMC / WLPMC) cover Olympiad → high-school →
US AMC → Putnam difficulty. We pull all of them and tag each entry with
its source for downstream stratification.

Output layout (mirrors WTQ / SearchQA shape)::

    data/benchmarks/livemathbench/
    ├── dataset.json                       # list of {id, instruction, answer, source, ...}
    └── question/
        └── <id>.txt                       # the problem statement (UTF-8)

dataset.json entry shape::

    {
      "id":            "lm-CNMO-0",
      "instruction":   "Find all real solutions to ...",
      "question_txt":  "question/lm-CNMO-0.txt",
      "answer":        "x = 2 + sqrt(3)",
      "answer_values": ["x = 2 + sqrt(3)"],
      "source":        "CNMO",
      "language":      "en",
      "question_type": "Problem-Solving",
    }

``answer_values`` is a 1-element list (compat shim with WTQ shape so the
diagnoser / momentum / patcher can read it uniformly).

Bench budget alignment: total ~119 problems × en (4 configs concatenated).
We deterministically shuffle and emit all of them; for SS/WTQ-style
40-train / 100-test split, n_test=80 leaves ~39 for training.

Run once::

    .venv/bin/python -m data.benchmarks.build_livemath_dataset
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path


SOURCES_EN = ["CNMO", "CCEE", "AMC", "WLPMC"]
HF_ID = "opencompass/LiveMathBench"


def _load_hf_config(hf_id: str, config: str, hf_token: str | None) -> list[dict]:
    """Load one (gated) config split from HF."""
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit(
            "datasets package not installed. "
            "Install with: .venv/bin/pip install datasets"
        )

    print(f"[livemath] loading {hf_id} config={config} ...")
    kwargs = {"split": "test"}
    if hf_token:
        kwargs["token"] = hf_token
    ds = load_dataset(hf_id, config, **kwargs)
    rows = list(ds)
    print(f"[livemath] {config}: {len(rows)} rows")
    return rows


def _to_skillgrad_entry(row: dict, slot: int, source: str, language: str) -> dict:
    """Convert one HF row to a SkillGrad-compatible dataset entry.

    HF row schema (LiveMathBench):
        {
          "question":       "<problem statement>",
          "answer":         "<gold answer>",
          "question_type":  "Problem-Solving" | "Fill-In-the-Blank",
          "language":       "en" | "cn",
          ...
        }
    """
    ex_id = f"lm-{source}-{slot}"
    return {
        "id":            ex_id,
        "instruction":   row["question"],
        "question_txt":  f"question/{ex_id}.txt",
        "answer":        row.get("answer", ""),
        "answer_values": [row.get("answer", "")],
        "source":        source,
        "language":      language,
        "question_type": row.get("question_type", "Problem-Solving"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--hf-id", default=HF_ID,
        help="HuggingFace dataset id (default: opencompass/LiveMathBench)",
    )
    ap.add_argument(
        "--version", default="v202412",
        help="LiveMathBench version tag (default: v202412)",
    )
    ap.add_argument(
        "--language", default="en", choices=["en", "cn"],
        help="Dataset language (default: en)",
    )
    ap.add_argument(
        "--output", default="data/benchmarks/livemathbench",
        help="Output directory for the SkillGrad-compatible layout.",
    )
    ap.add_argument(
        "--shuffle-seed", type=int, default=0,
        help="Deterministic shuffle seed before writing dataset.json.",
    )
    args = ap.parse_args()

    output = Path(args.output).resolve()
    hf_token = os.environ.get("HF_TOKEN")

    all_rows: list[tuple[str, dict]] = []
    for src in SOURCES_EN:
        config = f"{args.version}_{src}_{args.language}"
        try:
            rows = _load_hf_config(args.hf_id, config, hf_token)
        except Exception as e:
            print(f"[livemath] WARNING: failed to load {config}: {e}")
            continue
        all_rows.extend((src, r) for r in rows)

    print(f"[livemath] total raw rows: {len(all_rows)}")

    # Deterministic shuffle
    rng = random.Random(args.shuffle_seed)
    indices = list(range(len(all_rows)))
    rng.shuffle(indices)

    output.mkdir(parents=True, exist_ok=True)
    question_dir = output / "question"
    question_dir.mkdir(exist_ok=True)

    entries: list[dict] = []
    for slot, src_idx in enumerate(indices):
        source, row = all_rows[src_idx]
        entry = _to_skillgrad_entry(row, slot, source, args.language)
        entries.append(entry)
        q_path = output / entry["question_txt"]
        q_path.write_text(row["question"], encoding="utf-8")

    out_json = output / "dataset.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"[livemath] wrote {len(entries)} entries -> {out_json}")
    print(f"[livemath] question files in {question_dir}")
    if entries:
        print(f"[livemath] sample entry:\n{json.dumps(entries[0], ensure_ascii=False, indent=2)[:500]}")


if __name__ == "__main__":
    main()
