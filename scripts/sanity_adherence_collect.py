#!/usr/bin/env python3
"""Sanity check: within-group adherence variance signal viability."""
import json
import os
from pathlib import Path
import sys

# 5 judgeable rules from v8 SS-5.4 SKILL.md (one per H2 section, paraphrased)
RULES = {
    "R1_classify_deliverable": "Before writing output, did the rollout inspect workbook structure (sheet names, populated ranges, headers, examples) and classify the task as data-edit / formula-write / formatting / code-response?",
    "R2_layout_inspection": "Before mapping source-to-target, did the rollout inspect actual headers and sample rows to derive real source/target columns, rather than mapping by header text equality alone?",
    "R3_stateful_simulate": "If the task involved stateful traversal (scan with restart/skip/continue), did the rollout dry-run the traversal on a concrete sheet example before coding?",
    "R4_block_aware": "If the sheet had blank-separated regions, did the rollout detect blocks and operate per-block rather than over the whole used range?",
    "R5_verify_output": "After saving output.xlsx, did the rollout reopen and verify that evaluator-visible target cells contain exact expected final values (not formula-strings or stale state)?",
}

# 8 tasks across 4 failure-mode clusters (2 each)
TASKS = {
    "MODALITY_MISS": ["13284", "45300"],
    "VALUE_MISMATCH": ["32093", "37900"],
    "MODALITY_CONFUSION": ["22-47", "374-18"],
    "VERIFICATION_BLIND": ["230-16", "486-17"],
}

EVAL_DIR = "results/runs/g2b-v8_gpt-5.4/eval_100slice_multiseed"
OUT_DIR = Path("results/sanity_adherence")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_trace(tid: str, seed: int) -> str | None:
    p = Path(f"{EVAL_DIR}/task_{tid}_s{seed}/execution_trace_r0.md")
    if not p.exists():
        return None
    return p.read_text(errors="ignore")


def collect_rollouts() -> list[dict]:
    rollouts = []
    for fail_mode, tids in TASKS.items():
        for tid in tids:
            for seed in [0, 1, 2]:
                trace = load_trace(tid, seed)
                if trace is None:
                    print(f"  MISSING: {tid} seed {seed}", file=sys.stderr)
                    continue
                rollouts.append({
                    "task_id": tid,
                    "seed": seed,
                    "fail_mode": fail_mode,
                    "trace": trace,
                })
    return rollouts


if __name__ == "__main__":
    rollouts = collect_rollouts()
    print(f"  collected {len(rollouts)} rollouts (target 24)")
    import json as _j
    _j.dump([{**r, "trace_chars": len(r["trace"])} for r in rollouts],
            open(OUT_DIR / "rollouts_inventory.json", "w"), indent=2, default=str)
    print(f"  inventory at {OUT_DIR}/rollouts_inventory.json")
