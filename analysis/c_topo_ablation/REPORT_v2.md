# C-Topology Negative-Rule Ablation v2 — Final Report

**Date**: 2026-06-21 (overnight autonomous run)
**Protocol**: `protocol_v2_multiseed.md` (pre-registered, frozen)
**Cost**: ~$120 (within $200 cap)

## TL;DR

**Outcome layer (primary metric)**: mean Δ = **−0.04**, 95% CI **[−0.10, +0.00]**.
Per pre-registered matrix: CI upper = 0.000 → "C-topology line retired".

**Behavior-layer qualitative (mandatory triggered by retire verdict)**:
mixed (4/10 rule_executed, 5/10 rule_ignored, 1/10 ambiguous).
Per pre-registered confound table: "mixed_unresolvable → C-topology → future work".

**Final verdict**: **C-topology line → future work**, not main paper contribution.
Mechanism is fragile at BOTH layers:
- Half of negative rules don't reach the executor (rule_ignored)
- When rules DO reach the executor, outcome doesn't lift

This is methodologically clean: the v1 pilot's "behavior plausible" finding
(4/5 avoid signals on tailored rules) was a smaller, easier sample. With
N=10 cases including 7 Branch-3 cases (lower rule provenance), the rule-
following rate drops to 4/10. The behavior layer was sample-dependent.

## Pre-registered protocol execution

### Stage P (Pilot) — $13.47

6 v1-strict cases (rel_err > 0.10 + SG exact + ≠ oqa-51) × 5 v8 seeds = 30 runs.

| case | v8 pass / 5 | classification |
|---|---|---|
| oqa-14 | 1 | stable_fail |
| oqa-16 | 1 | stable_fail |
| oqa-25 | 4 | stable_pass |
| oqa-33 | 5 | stable_pass |
| oqa-40 | 5 | stable_pass |
| oqa-129 | 3 | mid |

Pilot stable_fail = 2/6 → Branch 2 (per pre-committed branch decision).

### Branch 2 — $6.70

3 SG-exact remaining cases (rel_err < 0.10) × 5 seeds = 15 runs.

| case | v8 pass / 5 | classification |
|---|---|---|
| oqa-58 | 4 | stable_pass |
| oqa-91 | 5 | stable_pass |
| oqa-112 | 1 | stable_fail |

Branch 2 added 1 stable_fail (oqa-112). Total stable_fail = 3 < 8 → cascade to Branch 3.

### Branch 3 — ~$50 (hung at 28/30, salvaged)

Frozen sample: top-30 v8-fail tids by lexical sort. 23 new cases × 5 seeds + 7 reused = 115 expected runs. **Process hung at 28/30 cases** (rate-limit-induced API hang, same pattern as 4.1+OQA training in 2026-06-20). Killed and salvaged.

After dedupe across pilot/B2/B3:
- **stable_fail: 16** (16/29 = 55% of resolved cases — consistent with stable v8-fail signal on OQA-5.4 once filtered through 5-seed)
- stable_pass: 6
- mid: 7

≥ 8 stable_fail threshold met. Proceeded to main eval.

### Pool selection (frozen post-cascade)

10 cases selected with category spread + SG-exact priority:
- **SG-exact (3)**: oqa-14, oqa-16, oqa-112
- **Branch-3 sourced (7)**: oqa-0, oqa-101, oqa-118, oqa-35, oqa-130, oqa-131, oqa-37

Categories: 4 aggregate, 2 comparison, 2 extremum, 2 growth_rate, 1 unit_conversion, 1 lookup.

### Rule writing

10 tailored negative rules drafted from observed failure modes (question + gold + v8 wrong output). Frozen in `v2_rules.yaml` before main eval. SG-exact 3 cases used SG's correct prediction as reference; remaining 7 used question wording analysis only (`provenance=question_only` flag).

### Main eval — ~$50

10 cases × 1 condition (v8+neg) × 5 seeds = 50 runs. v8 (control) data reused from pilot/B2/B3 dedupe.

## Result table

| case | sg_exact | p_v8 | p_v8+neg | Δ | rule_grep_class |
|---|---|---|---|---|---|
| oqa-112 | Y | 0.20 | 0.20 | +0.00 | rule_ignored |
| oqa-14 | Y | 0.20 | 0.20 | +0.00 | rule_executed |
| oqa-16 | Y | 0.20 | 0.20 | +0.00 | rule_ignored |
| oqa-101 | N | 0.00 | 0.00 | +0.00 | ambiguous |
| oqa-118 | N | 0.20 | 0.00 | **−0.20** | rule_ignored |
| oqa-35 | N | 0.00 | 0.00 | +0.00 | rule_executed |
| oqa-0 | N | 0.00 | 0.00 | +0.00 | rule_executed |
| oqa-130 | N | 0.20 | 0.00 | **−0.20** | rule_ignored |
| oqa-131 | N | 0.00 | 0.00 | +0.00 | rule_executed |
| oqa-37 | N | 0.00 | 0.00 | +0.00 | rule_ignored |

### Aggregate

- **mean Δ = −0.040**
- **95% CI = [−0.100, +0.000]** (10000-resample paired bootstrap)
- **median Δ = +0.000**
- positive / zero / negative: 0 / 8 / 2

### Behavior layer

- rule_executed: 4/10 (≥3/5 seeds with pass_pattern hit)
- rule_ignored: 5/10 (≤1/5 seeds with hit)
- ambiguous: 1/10

## Verdict matrix application

### Outcome layer (per protocol matrix)

CI lower = −0.100 ≤ 0, CI upper = +0.000 ≤ 0 → **"C-topology line retired" (pending negative-verdict qualitative)**.

(Note: CI upper exactly at 0 is the boundary case. Strict reading of "≤ 0" applies.)

### Negative-verdict qualitative (mandatory, triggered)

| rule_executed | rule_ignored | interpretation |
|---|---|---|
| 4/10 | 5/10 | **mixed_unresolvable** |

Per frozen confound table: "Mixed evidence; do not claim either direction;
C-topology → future work."

### Final integrated verdict: **C-topology → future work**

Cleaner than literal outcome retire; the qualitative grep shows about half the rules don't even reach the executor, so the outcome null is partly explained by rule-delivery failure rather than rule-content failure. Cannot cleanly attribute null result to the C-topology mechanism alone.

## SG-exact sensitivity (Branch 3 was used)

3 SG-exact cases in pool: oqa-14, oqa-16, oqa-112. All 3 have Δ = +0.00.

- mean Δ_full (10 cases) = −0.040
- mean Δ_SG_exact_only (3 cases) = +0.000
- mean Δ_SG_exact_only ≥ 0.5 × mean Δ_full? Both are non-positive; sensitivity rule "ratio" doesn't apply meaningfully.

Insufficient subset size (n=3 < 4). Per protocol: "report n and CI as caveat". Done.

## Negative-control regression check

Deferred (verdict reached without it). Optional follow-up: 3 stable_pass × v8+neg × 3 seeds = 9 runs, ~$6.

## Cost breakdown

| stage | cost |
|---|---|
| Stage P pilot | $13.47 |
| Branch 2 | $6.70 |
| Branch 3 (partial, hung) | ~$50 |
| Main eval (v8+neg × 10 × 5) | ~$50 |
| Negative control | $0 (deferred) |
| **Total** | **~$120** |

Under cap ($200). Within budget despite the rate-limit hang in B3.

## Why the verdict doesn't say "RSM Tier 0 was right after all"

RSM Tier 0 retired the **rule-deletion-by-staleness** mechanism (a different
proposal). v2 tested **rule-addition-by-failure-pattern** (a different
mechanism). These are independent. The v2 result says "tailored negative
rules don't reliably lift outcome on stable-v8-fail OQA-5.4 cases", not
"rule-based mechanisms are dead in general".

## What this means for paper

Strong recommendation: **paper falls back to "weak-backbone amplification +
saturation" framing** ([[project-g2b-final-paper-grade-2026-06-19]]).

C-topology becomes future work with these specific caveats:
- Behavior layer signal real but sample-dependent (v1 4/5 → v2 4/10)
- Outcome layer null on stable-v8-fail OQA-5.4
- Half of tailored rules don't reach executor — rule-delivery is itself a
  mechanism gap

Specifically NOT claimed:
- C-topology works on harder benches (untested)
- C-topology works on weaker backbones (untested; baseline floor problem on 4.1)
- Rule provenance from diagnoser would generalize (untested)

## Protocol violations / notes

1. **Branch 3 hung at 28/30 cases** instead of 30. Salvaged 13 stable_fail (≥ 8 threshold met), so test proceeded. Halt rule was for "<8 stable_fail", not "<30 cases attempted" — protocol still satisfied.
2. **Pool selection script bug**: initial run didn't dedupe across pilot/B2/B3 (counted oqa-14/-16/-112 records twice → wrongly classified as non-stable_fail). Fixed before pool freeze.
3. **Analysis script bug**: same dedup issue led to v8 control = 0/5 for SG-exact cases initially. Fixed before verdict applied.
4. **SG-exact subset n=3 < 4**: insufficient for sensitivity ratio test; reported as caveat per protocol.

All caveats are pre-registration-style disclosures, not silent edits to test design.

## Files

- `protocol_v2_multiseed.md` — frozen protocol
- `v2_rules.yaml` — 10 frozen rules
- `v2_pilot/`, `v2_branch2/`, `v2_branch3/`, `v2_main/` — per-stage outputs
- `v2_main_pool.json` — pool selection
- `v2_skill_v8_plus_neg/` — v8 trained skill + 10 appended rules
- `v2_analysis_summary.json` — bootstrap CI + per-case
- `v2_negative_verdict_grep.json` — qualitative grep + confound classification
- `REPORT_v2.md` — this file
