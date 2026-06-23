"""Q1 Jaccard threshold replay — read v8 fix-run diagnoses, extract
CONVERGENT all_fail per-task entries, simulate `applies_when`,
compute pairwise token-Jaccard for cross-task pairs, emit:
  - histogram of Jaccard values
  - per-threshold cross-task pair counts
  - 10 anonymized sample pairs at each threshold {0.2..0.7}
  - frozen labeling criterion + manual-review template

OUT: analysis/c_topo_patcher_v1/jaccard_calibration.md
     analysis/c_topo_patcher_v1/jaccard_pairs.json (full data)

The script does NOT pick a threshold. Threshold pick happens AFTER
manual labeling of the 10 sample pairs per threshold.

Deterministic re-run: same input → same output (no randomness except
the seeded sample selection).
"""
from __future__ import annotations
import json
import re
import random
from pathlib import Path
from collections import defaultdict


RUNS = [
    "g2b-v8_gpt-4.1_ss-gpt41-fix",
    "g2b-v8_gpt-4.1_wtq-gpt41-fix",
    "g2b-v8_gpt-4.1_oqa-gpt41-smoke",
    "g2b-v8_gpt-5.4_oqa-gpt54-smoke",
]
SAMPLE_SEED = 42
N_SAMPLE_PER_BIN = 10
THRESHOLDS = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
APPLIES_WHEN_CHARS = 200  # first 200 chars after LABEL: simulate applies_when

# Anonymization patterns — applied BEFORE Jaccard so threshold doesn't reward shared bench/ids
ANON = [
    (re.compile(r"\boqa-\d+\b", re.I), "<TID>"),
    (re.compile(r"\bnt-\d+\b", re.I), "<TID>"),
    (re.compile(r"\b\d{5,}\b"), "<NUM>"),     # 5+ digit task-id-ish numbers
    (re.compile(r"\bspreadsheetbench\b|\bspreadsheet bench\b|\bxlsx\b", re.I), "<bench>"),
    (re.compile(r"\bwikitablequestions\b|\bwtq\b", re.I), "<bench>"),
    (re.compile(r"\bofficeqa\b|\btreasury bulletin[s]?\b", re.I), "<bench>"),
    (re.compile(r"\btreasury_bulletin_\d{4}_\d{2}\.txt\b", re.I), "<srcfile>"),
]

# Diagnose entry pattern: H2 header + free-text body until next H2
H2_RE = re.compile(
    r"^## \[Evidence E\d+, tier=([^\]]+)\] Task (\S+) \(([^,]+), accuracy: ([\d.]+)%?\)$",
    re.M,
)


def anonymize(text: str) -> str:
    for pat, rep in ANON:
        text = pat.sub(rep, text)
    return text


def extract_diagnoses(md_path: Path) -> list[dict]:
    """Return list of {task_id, group_type, tier, label, applies_when, raw_body}."""
    if not md_path.exists():
        return []
    text = md_path.read_text(encoding="utf-8", errors="replace")
    matches = list(H2_RE.finditer(text))
    out = []
    for i, m in enumerate(matches):
        tier, task_id, group_type, _ = m.groups()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()

        # Convergence label: explicit CONVERGENT/DIVERGENT in first 400 chars
        head = body[:400].upper()
        if "CONVERGENT" in head and "DIVERGENT" not in head:
            convergence = "CONVERGENT"
        elif "DIVERGENT" in head:
            convergence = "DIVERGENT"
        else:
            convergence = "UNTAGGED"

        # LABEL line
        lbl_m = re.search(r"^LABEL:\s*(.+)$", body, re.M)
        label = lbl_m.group(1).strip() if lbl_m else ""

        # Simulated applies_when: first non-LABEL paragraph, first 200 chars
        if lbl_m:
            after_label = body[lbl_m.end():].strip()
        else:
            after_label = body
        applies_when_raw = after_label[:APPLIES_WHEN_CHARS]
        applies_when = anonymize(applies_when_raw).strip()

        out.append({
            "task_id": task_id,
            "group_type": group_type,
            "tier": tier,
            "convergence": convergence,
            "label": label,
            "applies_when": applies_when,
        })
    return out


def tokens(s: str) -> set[str]:
    s = s.lower()
    s = re.sub(r"[^\w<>]+", " ", s)
    return set(t for t in s.split() if len(t) >= 3)  # drop very short tokens


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / max(len(a | b), 1)


def main():
    out_root = Path("analysis/c_topo_patcher_v1")
    out_root.mkdir(parents=True, exist_ok=True)

    # ─── Load all diagnoses ────────────────────────────────────────
    all_entries: list[dict] = []
    for run in RUNS:
        for iter_n in range(1, 11):
            md = Path(f"results/runs/{run}/train/iter_{iter_n}/batch_diagnoses.md")
            if not md.exists():
                continue
            for e in extract_diagnoses(md):
                e["run"] = run
                e["iter"] = iter_n
                e["src_id"] = f"{run}/iter{iter_n}/{e['task_id']}"
                all_entries.append(e)

    print(f"loaded {len(all_entries)} diagnose entries from {len(RUNS)} runs")

    # Filter to function-rule candidates: CONVERGENT all_fail, with non-empty applies_when
    func_candidates = [
        e for e in all_entries
        if e["convergence"] == "CONVERGENT"
        and "all_fail" in e["group_type"]
        and len(e["applies_when"]) >= 30
    ]
    print(f"function-rule candidates (CONVERGENT all_fail): {len(func_candidates)}")

    # ─── Pairwise Jaccard on cross-task pairs ──────────────────────
    pairs = []
    for i, a in enumerate(func_candidates):
        ta = tokens(a["applies_when"])
        for j in range(i + 1, len(func_candidates)):
            b = func_candidates[j]
            if a["task_id"] == b["task_id"]:
                continue  # cross-task only
            tb = tokens(b["applies_when"])
            j_score = jaccard(ta, tb)
            pairs.append({
                "a_src_id": a["src_id"], "b_src_id": b["src_id"],
                "a_applies_when": a["applies_when"],
                "b_applies_when": b["applies_when"],
                "jaccard": j_score,
            })
    pairs.sort(key=lambda p: -p["jaccard"])
    print(f"cross-task pairs computed: {len(pairs)}")

    # ─── Histogram + per-threshold counts ──────────────────────────
    histogram = defaultdict(int)
    for p in pairs:
        bin_lo = round(p["jaccard"] * 10) / 10
        histogram[bin_lo] += 1

    threshold_counts = {t: sum(1 for p in pairs if p["jaccard"] >= t) for t in THRESHOLDS}

    # ─── Sample 10 anonymized pairs per threshold band ─────────────
    rng = random.Random(SAMPLE_SEED)
    sample_per_band: dict[str, list[dict]] = {}
    for i, t in enumerate(THRESHOLDS):
        upper = THRESHOLDS[i + 1] if i + 1 < len(THRESHOLDS) else 1.01
        band_pairs = [p for p in pairs if t <= p["jaccard"] < upper]
        if len(band_pairs) > N_SAMPLE_PER_BIN:
            sample = rng.sample(band_pairs, N_SAMPLE_PER_BIN)
        else:
            sample = list(band_pairs)
        sample_per_band[f"{t:.1f}-{upper:.2f}"] = sample

    # ─── Emit JSON full data ────────────────────────────────────────
    (out_root / "jaccard_pairs.json").write_text(
        json.dumps({
            "n_diagnoses": len(all_entries),
            "n_func_candidates": len(func_candidates),
            "n_pairs": len(pairs),
            "histogram": {f"{k:.1f}": v for k, v in sorted(histogram.items())},
            "threshold_counts": threshold_counts,
            "sample_per_band": sample_per_band,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # ─── Emit calibration markdown for review ──────────────────────
    md = []
    md.append("# Jaccard Threshold Calibration — replay output\n")
    md.append(f"**Source**: 4 v8 fix runs, all `batch_diagnoses.md` 1-10 iter\n")
    md.append(f"**Diagnose entries loaded**: {len(all_entries)}\n")
    md.append(f"**Function-rule candidates** (CONVERGENT all_fail, applies_when ≥30 chars): {len(func_candidates)}\n")
    md.append(f"**Cross-task pairs**: {len(pairs)}\n\n")

    md.append("## Jaccard distribution (rounded to 0.1)\n\n")
    md.append("| Jaccard bin | count |\n|---|---|\n")
    for k in sorted(histogram):
        md.append(f"| {k:.1f} | {histogram[k]} |\n")
    md.append("\n")

    md.append("## Cross-task pair count above each threshold\n\n")
    md.append("| threshold | n_pairs | % of total |\n|---|---|---|\n")
    for t in THRESHOLDS:
        n = threshold_counts[t]
        pct = 100 * n / max(len(pairs), 1)
        md.append(f"| ≥ {t:.1f} | {n} | {pct:.1f}% |\n")
    md.append("\n")

    # ─── Frozen labeling criterion + manual review template ────────
    md.append("## FROZEN labeling criterion (DO NOT modify after pair inspection)\n\n")
    md.append(
        '> A pair is **`same_trigger`** iff: a single `applies_when` clause '
        '(generic, ≤30 words, no dataset literals) could be written that '
        'covers BOTH diagnoses\' failure conditions. The pair is '
        '**`different_trigger`** iff such a unified clause would either '
        'be too generic to be actionable, OR would have to enumerate '
        'unrelated cases. **`unclear`** is the third option only when '
        'the diagnoses are too short / unparseable to judge.\n\n'
        "Rule: judge based on the anonymized `applies_when` text alone. "
        "Do NOT consult task_id, bench, label, or run id. Do NOT change "
        "this criterion after seeing pairs.\n"
    )

    md.append("\n## Anonymized sample pairs per band — fill `judgment` column\n\n")
    for band, sample in sample_per_band.items():
        md.append(f"### Band Jaccard {band}\n\n")
        if not sample:
            md.append("(no pairs in this band)\n\n")
            continue
        for i, p in enumerate(sample, 1):
            md.append(f"**Pair {i}** (J={p['jaccard']:.2f})\n\n")
            md.append(f"- A applies_when: `{p['a_applies_when']}`\n")
            md.append(f"- B applies_when: `{p['b_applies_when']}`\n")
            md.append(f"- judgment: `[ ]` same_trigger / `[ ]` different_trigger / `[ ]` unclear\n\n")
        md.append("\n")

    md.append("## Decision protocol (apply AFTER labeling all sample pairs)\n\n")
    md.append(
        "Threshold T = lowest value where:\n"
        "1. precision ≥ 0.7 (≥7/10 sample pairs labeled `same_trigger`)\n"
        "2. recall not catastrophically low (≥3/10 of band ≥T are `same_trigger`)\n\n"
        "If multiple T satisfy, pick the LOWER T (favor recall).\n"
        "If no T satisfies → fall back to **0.3 default** AND flag in SCHEMA Section 2 as caveat.\n"
    )

    (out_root / "jaccard_calibration.md").write_text("".join(md), encoding="utf-8")
    print(f"\nWrote: {out_root/'jaccard_calibration.md'}")
    print(f"       {out_root/'jaccard_pairs.json'}")


if __name__ == "__main__":
    main()
