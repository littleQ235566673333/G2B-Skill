# RSM Tier 0 — Final Report

**Date**: 2026-06-20
**Question**: is anti-wipe over-protective on at least some wipe events
("stale_cleanup")? Should we build Tier 1 (rule-level provenance + selective revert)?
**Answer**: **No. Drop the RSM line.** Anti-wipe is destructive-content-protector
in 94% of observed events; over-protection signal is below the pre-committed
30% threshold.

## Decision per pre-committed dual rule

| criterion | threshold | observed | passed? |
|---|---|---|---|
| ① at least one event verdict ≠ destructive | ≥1 | 1 (ambiguous, 0 stale_cleanup) | ✓ |
| ② cluster of non-destructive verdicts | ≥30% of events | 6.25% (1/16) | ✗ |

Both must pass to justify Tier 1. Criterion ② fails. **Decision: stop.**

## Tally

| Stratum | total | destructive | stale_cleanup | ambiguous |
|---|---|---|---|---|
| **A** (anti-wipe engaged, intercepted) | 8 | 7 | 0 | 1 |
| **B** (no anti-wipe, silent wipe) | 8 | 8 | 0 | 0 |
| **Total** | 16 | 15 | 0 | **1** |

## What the data shows

### Stratum A — wipe attempts the guard caught

Pattern: in every Stratum A event, the patcher wrote a **wholesale replacement** of an already-developed skill, much smaller than the prior version (write_size / pre_size between 9% and 43%, median 16%). Even when the patcher's self-summary described the patch as "incremental additions" (header mapping, score parsing, etc.), the actual write replaced the entire file with the additions only — the accumulated content from prior iterations would have been lost.

Anti-wipe correctly intercepted these in 7/8 cases. The 1 ambiguous case (`g2b-v8_gpt-4.1_wtq-gpt41-fix iter 2`) was at iter 2 (early), 43% size ratio (just under the threshold), and the patcher's described content was genuinely new — at this early stage the loss would have been smaller. Even there, the call leans destructive but I marked ambiguous to avoid over-counting.

### Stratum B — what an unintervened wipe actually deletes

Pattern: deleted lines are concrete useful patterns that match real failure modes. Examples:
- `skillgrad_gpt-4.1_oqa-gpt41-smoke iter 1`: deleted `Numerical answers: digits only` rule — exactly the kind of formatting rule the executor needs.
- `skillgrad_gpt-4.1_oqa-gpt41-smoke iter 7`: deleted `always write the computed answer to the designated output cell` — a critical output-side rule.
- `g2b-v8_gpt-4.1_wtq-gpt41 iter 4`: deleted multi-column row scanning, synonym header matching, atomic entity treatment — foundational WTQ guidance from iters 1-3.

In 0/8 events did the wipe remove content that looked redundant or stale. Every wipe was destructive on inspection.

### `next_iter_pass_count_delta` — observational, uninformative

As predicted in the template:
- Mean Δ across all events: ~0
- Range: −1 to +1
- 4.1+OfficeQA baseline is 0%, so per-iter pass-count Δ is always near zero regardless of what was deleted.

Confirms the design choice to NOT use Δ as a verdict signal. Spot-check on rule content was the only informative path.

## Caveats

1. **Verdicts are LLM-judgment** (Claude, offline). This is structurally different from the in-loop LLM-judge ruled out by [[project-g2b-ptb-step2-terminated]] and [[feedback-discrete-retrieval-backbone-split]] (which would have driven mid-training decisions), but it is not human ground truth. A user spot-check of 16 events (~30 minutes) could revise.

2. **Stratum A verdicts inferred from patcher self-summary**, not from actual wipe content (reverted). Anchored on size ratio: a sub-50% rewrite of a developed skill is the wipe signature, regardless of stated intent. If user disagrees with this anchor, spot-check the actual `iter_N/patcher.jsonl` events.

3. **Sample composition skewed to OfficeQA-tinged data**: 6 of 16 events come from 4.1+OfficeQA runs (3 SG + 1 v8-FIX + 2 inferred). 4.1+OfficeQA has 0% baseline, which suppresses Δ signal more than other configs. SS/WTQ wipes (10 events) have similar verdict distribution though, so the conclusion likely generalizes.

4. **Tier 0 cannot answer counterfactuals**: we don't know if a Tier 1 (rule-level revert that preserves parts of a wipe-attempt) would have outperformed full revert. Tier 0 only shows that whole-file revert is rarely wrong; rule-level revert MIGHT recover the 1 ambiguous case but at the cost of building infrastructure for ~6% of events.

## What this means for the paper / next steps

- **Anti-wipe stays as is**: the simple 50%-shrink + revert guard is correct in 94% of observed cases. No need for rule-level provenance, no need for protection_level field, no need for evidence_support tracking.
- **RSM line is closed**. Move on.
- **Paper claim**: anti-wipe is a clean weak-backbone-specific intervention on a wipe failure mode that affects both v8 (frequent) and SkillGrad (on harder benches). The fix is small, mechanical, and high-coverage.

## Files

- `analysis/rsm_tier0/template.md` — design / decision rule (pre-committed)
- `scripts/rsm_tier0_collect.py` — auto-fill quantitative fields from training_results.json + snapshots + patcher.jsonl
- `scripts/rsm_tier0_render.py` — render events into spot-check md
- `scripts/rsm_tier0_verdict.py` — apply (provisional) verdicts
- `analysis/rsm_tier0/events_auto.yaml` — quantitative auto-fill (16 events)
- `analysis/rsm_tier0/events_filled.yaml` — events + verdicts + caveats
- `analysis/rsm_tier0/events_spotcheck.md` — human-readable spot-check view (per-event detail)
- `analysis/rsm_tier0/REPORT.md` — this report

## Cumulative cost (Tier 0 analysis only)

$0 (offline analysis on existing run artifacts).
