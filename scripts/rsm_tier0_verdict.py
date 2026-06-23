"""Apply provisional verdicts to events_auto.yaml → events_filled.yaml.

Verdicts assigned by Claude (offline meta-analysis, NOT in-loop LLM-judge).
Disclosed limitation: this IS LLM judgment, just structured + offline.
User can override by editing the file directly.

Decision logic per template.md:
  - destructive: deleted content was useful (covers known failure modes)
  - stale_cleanup: deleted content was redundant / contradicted by newer
  - ambiguous: when unsure

For Stratum A (reverted): based on (a) write_size / pre_size ratio
  (a wholesale rewrite that would lose 70%+ of accumulated knowledge is
  destructive even if some new content is added), and (b) patcher's
  self-summary content where readable.

For Stratum B (visible deletions): based on whether the deleted_rule_texts
  describe useful patterns (yes for nearly all observed cases).
"""

from __future__ import annotations

from pathlib import Path

import yaml


VERDICTS = {
    # (run_id, iter): (verdict, notes)
    ("g2b-v8_gpt-4.1_oqa-gpt41-smoke", 3): (
        "destructive",
        "Patcher tried to write 700B replacing 5697B. Even if new Gini-coefficient "
        "section is genuine, dropping to 12% of pre means ~88% of accumulated rules "
        "would be lost. Wholesale-rewrite signature."
    ),
    ("g2b-v8_gpt-4.1_ss-gpt41-fix", 3): (
        "destructive",
        "1120B vs 7195B (16%). Patcher self-described header-mapping additions, but "
        "wholesale rewrite would have lost 84% of prior content."
    ),
    ("g2b-v8_gpt-4.1_ss-gpt41-fix", 8): (
        "destructive",
        "1724B vs 18591B (9%). Tiny rewrite of a fully-developed skill; multi-row "
        "header + literal-value rules described as 'incremental' but written as wipe."
    ),
    ("g2b-v8_gpt-4.1_ss-gpt41-fix", 9): (
        "destructive",
        "2052B vs 18591B (11%). Same wipe pattern as iter 8."
    ),
    ("g2b-v8_gpt-4.1_wtq-gpt41-fix", 2): (
        "ambiguous",
        "2167B vs 5005B (43%). Just under 50% threshold. Patcher's described content "
        "(schema inspection, 'next' disambiguation) is genuinely new and applicable. "
        "Hard to call destructive vs reorganization — would have lost ~57% but at "
        "this early iter the loss is less catastrophic. Borderline; conservative call."
    ),
    ("g2b-v8_gpt-4.1_wtq-gpt41-fix", 5): (
        "destructive",
        "2929B vs 10051B (29%). Same pattern; would lose 71% of accumulated."
    ),
    ("g2b-v8_gpt-4.1_wtq-gpt41-fix", 6): (
        "destructive",
        "1264B vs 10051B (13%). Tiny rewrite."
    ),
    ("g2b-v8_gpt-4.1_wtq-gpt41-fix", 9): (
        "destructive",
        "3428B vs 14593B (23%). Wholesale rewrite signature."
    ),
    # Stratum B (visible deletions)
    ("g2b-skill-spreadsheet_gpt-4.1_v6", 4): (
        "destructive",
        "Deleted: N-way region matching, ws.max_row overcounting pitfall, multi-key "
        "join logic. All concrete useful spreadsheet patterns."
    ),
    ("g2b-skill-wtq_gpt-4.1_v6", 6): (
        "destructive",
        "Deleted: max-entity selection, single-vs-set answer disambiguation, "
        "multi-constraint AND-filter. Core WTQ guidance."
    ),
    ("g2b-v8_gpt-4.1_ss-gpt41", 7): (
        "destructive",
        "Deleted: enumerate-sheet-headers rule, aggregation_preserve_fields ref "
        "pointer, next-row-condition fill rule. All from iter 3-5, recently introduced."
    ),
    ("g2b-v8_gpt-4.1_wtq-gpt41", 4): (
        "destructive",
        "Deleted: multi-column row scanning, synonym header matching, atomic-entity "
        "treatment. Foundational WTQ patterns from iter 1-3."
    ),
    ("g2b-v8_gpt-4.1_wtq-gpt41", 8): (
        "destructive",
        "Deleted: multi-condition aggregation, linked entity counting, numeric "
        "coercion (pd.to_numeric). Concrete actionable rules."
    ),
    ("skillgrad_gpt-4.1_oqa-gpt41-smoke", 1): (
        "destructive",
        "Deleted YAML frontmatter description + 'Numerical answers: digits only' "
        "rule + skill body intro. Critical formatting + scope info lost. "
        "(Note: next-iter delta = +1, but this is GPT-5.4-level baseline noise on "
        "OfficeQA, not signal of stale-cleanup.)"
    ),
    ("skillgrad_gpt-4.1_oqa-gpt41-smoke", 5): (
        "destructive",
        "Deleted: multi-table aggregation error pitfall, table_extraction_validation "
        "ref, precise-match confirmation. Multi-rule loss."
    ),
    ("skillgrad_gpt-4.1_oqa-gpt41-smoke", 7): (
        "destructive",
        "Deleted: 'always write computed answer to output cell' rule (output-format "
        "critical), skill description, table_extraction reference. Output-side rules "
        "are exactly what should NOT be wiped."
    ),
}


def main() -> None:
    src = Path("analysis/rsm_tier0/events_auto.yaml")
    dst = Path("analysis/rsm_tier0/events_filled.yaml")
    d = yaml.safe_load(src.read_text(encoding="utf-8"))
    events = d["events"]

    n_filled = 0
    for e in events:
        key = (e["run_id"], e["iter"])
        if key in VERDICTS:
            verdict, notes = VERDICTS[key]
            e["my_verdict"] = verdict
            e["verdict_notes"] = notes
            n_filled += 1

    d["events"] = events
    d["verdict_meta"] = {
        "verdict_provisional": True,
        "verdict_assigned_by": "claude (offline meta-analysis, structured per template.md)",
        "verdict_caveat": (
            "These verdicts are LLM-judgment applied offline, distinct from the "
            "in-loop LLM-judge that PTB Step 2 ruled out. User should review and "
            "override; spot-checking 16 events takes ~30 minutes."
        ),
    }

    dst.write_text(
        yaml.safe_dump(d, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
    )
    print(f"Filled {n_filled}/{len(events)} verdicts → {dst}")

    # Tally
    from collections import Counter
    by_verdict = Counter(e.get("my_verdict") for e in events)
    by_stratum_verdict: dict[tuple[str, str], int] = {}
    for e in events:
        k = (e["stratum"], e.get("my_verdict") or "unfilled")
        by_stratum_verdict[k] = by_stratum_verdict.get(k, 0) + 1
    print("\nBy verdict:")
    for v, c in by_verdict.most_common():
        print(f"  {v}: {c}")
    print("\nBy stratum × verdict:")
    for (s, v), c in sorted(by_stratum_verdict.items()):
        print(f"  {s} × {v}: {c}")


if __name__ == "__main__":
    main()
