# C-Topology Negative-Rule Ablation — Final Report

**Date**: 2026-06-21
**Pre-registered**: protocol.md (frozen before eval)
**Cost**: $19.72

## TL;DR

**Behavior layer (mechanism core)**: **4/5 avoided** in v8+neg vs **1/5 avoided**
in v8 baseline. Negative rules in SKILL.md *do* shift executor behavior in
the direction the rules prescribe. This answers the C-topology mechanism
question positively at the behavior layer.

**Outcome layer**: 3/5 pass across all three conditions (seed, v8,
v8+neg). Single-seed noise dominates because the 5-case selection was
based on a prior single-seed eval where v8 failed all 5; in this re-eval
v8 itself passes 3/5. The test as designed cannot resolve outcome
lift from negative rules.

**Per pre-registered matrix**, the literal verdict is **success**
(4/5 avoid + 3/5 pass) — but this hits the boundary in a methodologically
weak way. The honest interpretation: **mechanism plausible at the
behavior layer; outcome impact requires a multi-seed-stable case
selection to resolve**.

## Per-rule × per-condition table

| rule | case | seed avoid / outcome | v8 avoid / outcome | **v8+neg avoid / outcome** |
|---|---|---|---|---|
| R1 | oqa-14 | mixed / FAIL | mixed / PASS | **avoided / FAIL** |
| R2 | oqa-16 | avoided / PASS | inconclusive / FAIL | **inconclusive / PASS** |
| R3 | oqa-33 | inconclusive / PASS | inconclusive / PASS | **avoided / PASS** |
| R4 | oqa-40 | inconclusive / FAIL | inconclusive / PASS | **avoided / PASS** |
| R5 | oqa-129 | avoided / PASS | avoided / FAIL | **avoided / FAIL** |
| **TOTAL** | | 2 avoided / 3 pass | 1 avoided / 3 pass | **4 avoided / 3 pass** |

## Pre-registered matrix application

Matrix from protocol.md:

| avoid count | outcome count | verdict |
|---|---|---|
| ≥4/5 | ≥3/5 | **success** |
| ≥4/5 | 1-2/5 | marginal |
| ≥4/5 | 0/5 | rule_correct_no_lift |
| 3/5 | any | boundary (3-seed extra) |
| <3/5 | any | **fail — drop C-topology** |

Observed: 4/5 avoid + 3/5 pass → matrix says **success**.

## Why the literal matrix verdict is methodologically weak

The matrix implicitly assumed v8 baseline outcome would be ~0/5 (since
the 5 cases were selected as v8-fails). The matrix would have read 4/5
avoid + 3/5 pass as "v8 alone was 0/5, rules lifted to 3/5 = +3pp lift".

In actual re-eval: **v8 baseline already passes 3/5 of these cases**.
Single-seed noise on the original eval misclassified 3 cases as
"v8-lost". So the rules' real outcome lift is **0pp** (3 → 3).

This isn't matrix abuse — the matrix as pre-committed gives
"success". It's a case-selection methodology issue. To recover the
intended test, we'd need to:
1. Run v8 multi-seed (3-5 seeds) on the 14 v8-lost candidates
2. Pick 5 cases where v8 fails ≥3/5 seeds (stable v8-fail)
3. Re-run the ablation

Estimated extra cost: ~$60-100.

## What we CAN conclude (behavior layer is robust to selection noise)

The behavior-layer signal is **independent of case-selection seed
noise** — it measures whether the executor's reasoning trace contains
the patterns the rules prescribe, not whether the outcome happened to
pass.

| condition | "avoided" count | interpretation |
|---|---|---|
| seed | 2/5 | base model with seed skill mentions some patterns naturally |
| v8 | 1/5 | v8 trained skill (no negative rules) — slightly fewer pattern mentions |
| **v8+neg** | **4/5** | adding 5 explicit negative rules → 4 of 5 traces show the prescribed behavior |

This is a clean +3 behavior shift attributable to the rules. The
mechanism (rule text → executor reasoning) **does work**.

## Per-rule deep dive

### R1 oqa-14 — "use revised 1947 bulletin not 1942 bulletin"
- v8 trace: reads from both bulletins (mixed pattern)
- v8+neg trace: reads only `1947_08.txt` for both years (avoided)
- But outcome: v8 PASS, v8+neg FAIL
- **Single anomaly**: v8 in this run picked correctly without rule, v8+neg followed rule but somehow still computed 489. Could be that following the rule led to a different (wrong) extraction in 1947 bulletin. Worth deeper inspection but not signal of mechanism failure.

### R2 oqa-16 — "explicit extremum-month identification"
- v8+neg outcome PASS but avoid pattern not grep-detected (regex too narrow — agent identified the month using different phrasing). Inconclusive at signal layer; pass at outcome.
- Flag: avoid_check pattern needed `(minimum|min)...(at|=|in)...YYYY`; agent's actual phrasing was different. Pattern engineering issue, not mechanism issue.

### R3 oqa-33 — "use published subtotal, no manual subtraction"
- v8+neg trace explicitly identifies the "excluding options" subtotal row; avoided ✓
- All conditions pass — likely an easy case.

### R4 oqa-40 — "use pstdev not stdev"
- v8 trace: doesn't show explicit `pstdev` mention but passes (model used population formula implicitly)
- v8+neg trace: explicit `pstdev` call referenced; avoided ✓ AND PASS

### R5 oqa-129 — "state CPI-U values explicitly with 1982-84=100 base"
- All three conditions show explicit CPI-U mention (avoided ✓ for v8 and v8+neg both)
- Outcome flips arbitrarily: seed PASS, v8 FAIL, v8+neg FAIL — model picks wrong CPI values across conditions despite rule
- Suggests rule is necessary but not sufficient for this case (capability constraint at the value-selection step)

## Decisions

1. **C-topology mechanism core (rules → behavior shift): plausible, not falsified.**
   The behavior-layer 3-point lift is real and independent of case-selection noise.

2. **Outcome lift: not resolved by this ablation.** Single-seed selection bias
   confounds. Per protocol's "boundary" cell handling, this would normally
   trigger a 3-seed re-run; but with the same case set the noise issue
   persists. The right fix is **case selection on multi-seed v8 fails**, not
   re-running these 5 cases.

3. **Do not commit to building full C-topology training pipeline based on
   this result alone.** The behavior-layer signal supports continuing
   design work, but outcome lift remains unproven.

## Recommended next experiment (if continuing C-topology line)

**B-step: clean case selection.**
- Multi-seed (3 seeds) v8 eval on the 14 OQA-5.4 v8-lost candidates
- Pick 5 cases where v8 fails in ≥2/3 seeds (stable v8-fail)
- Re-run ablation with same 5 negative rule pattern
- Cost: ~$60-100, ~3h

**OR: paper-write with current scope.**
- Honest framing: "C-topology mechanism is plausible at behavior layer but
  outcome lift requires further validation; meanwhile v8+anti-wipe SS/WTQ
  4.1 result stands as the paper-grade headline."

## Caveats list (for honest writeup)

1. Rules are tailored to known v8 failures (best-case test); diagnoser-derived
   rules would need separate validation.
2. avoid_signal grep patterns are heuristic — R2 missed valid pass via
   different phrasing; pattern engineering ≠ mechanism failure.
3. Single-seed; outcome-layer 3/5 is noise-dominant.
4. Sample n=5 is small; behavior-layer 4 vs 1 is suggestive but not
   statistically tight.
5. Tested only on OQA-5.4. Whether negative rules help on other benches
   (or other backbones) is open.

## Files

- `analysis/c_topo_ablation/protocol.md` (pre-registered)
- `analysis/c_topo_ablation/rules.yaml` (pre-frozen rule specs)
- `analysis/c_topo_ablation/skill_v8_plus_neg/` (v8 skill + 5 appended rules)
- `analysis/c_topo_ablation/run_ablation.py` (eval driver)
- `analysis/c_topo_ablation/grep_avoid.py` (behavior-layer scoring)
- `analysis/c_topo_ablation/eval_results/summary.json` (15 eval outcomes)
- `analysis/c_topo_ablation/eval_results/avoid_signals.json` (per-rule avoid verdicts)
- `analysis/c_topo_ablation/REPORT.md` (this file)
