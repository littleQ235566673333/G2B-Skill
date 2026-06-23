# OfficeQA Bad Case Analysis — 2026-06-20

## TL;DR

**v8 underperforms SG on OfficeQA + GPT-5.4 by 4pp (49 vs 53), and by single-seed
the gap is within noise — but the failure mode is *not* random noise.**

On the 14 cases where SG passed and v8 failed (gold parseable):
- **SG median relative error = 0.0000** (14/14 exact match, mostly within
  the bench's 1% fuzzy tolerance).
- **v8 median relative error = 17.73%** (0/14 within 1%; **5/14 are >50% off**).

v8 isn't "close-but-wrong". v8 picks the **wrong source, wrong period, wrong
row, or wrong formula entirely**. This is consistent across the 15-task lost-set
and matches the existing process-vs-function mechanism finding.

## Cross-tab (5.4, 100-task heldout, single seed)

| | seed 5.4 | SG 5.4 | v8 5.4 |
|---|---|---|---|
| pass | 46 | 53 | 49 |

Per-task pass matrix (n=100):

| seed | SG | v8 | count | bucket |
|---|---|---|---|---|
| ✓ | ✓ | ✓ | 32 | all-easy |
| ✗ | ✗ | ✗ | 33 | all-hard |
| ✓ | ✓ | ✗ | **7** | **v8 regressed from seed (also helped by SG)** |
| ✓ | ✗ | ✗ | 3 | both methods regressed |
| ✓ | ✗ | ✓ | 4 | SG regressed, v8 OK |
| ✗ | ✓ | ✗ | **8** | **SG learned, v8 didn't** |
| ✗ | ✓ | ✓ | 6 | both learned |
| ✗ | ✗ | ✓ | 7 | only v8 learned |

**v8 net loss vs SG = (15 lost) - (11 won) = -4pp**.

## v8 failure mode — 5/14 are wholly wrong

```
tid       gold         SG predicted     v8 predicted     v8 rel_err
oqa-15    3069         3067 ✓           196212           62.93x   ← format mismatch
oqa-16    92000000     92000000 ✓       570000000        5.20x    ← wrong table
oqa-129   264.632      264.632 ✓        986.622          2.73x    ← wrong fiscal-year scope
oqa-14    142          142 ✓            489              2.44x    ← wrong source
oqa-2     1608.80%     1606.11% ✓       660.94           0.59x    ← wrong period AND missing %
```

These aren't computation bugs — they're **scope identification failures**: which
table, which row label, which time range. SG's skill nails them; v8's misses.

The remaining 9/14 are also wrong but smaller (5-25%): off-by-period or
off-by-formula choice (`pstdev` vs `stdev`, "FY" vs calendar year, etc.). Same
class, smaller magnitude.

## Why v8 misses what SG hits

The training-emerged SKILL.md content explains it directly:

**SG (270 lines, dense narrative)** — function-level rules:
> "When debt-limitation or grouped maturity tables contain nested totals
> and repeated labels, rewrite the exact target row path in words and confirm
> the extracted cell belongs to that full path and block, not just to a
> nearby Total marketable or repeated Total row."

> "When the prompt names a published aggregate such as gross debt,
> interest-bearing debt, or another bulletin-native measure, search for that
> named total first before constructing it from components."

> "For wording-defined statistics, reconstruct the full definition from the
> prompt before coding rather than stopping at a nearby default statistic;
> for example, coefficient of variation requires both the dispersion term
> and its mean denominator, not just the standard deviation."

**v8 (392 lines, more structured)** — process-level rules:
> "Classify the evidence before choosing an operation"
> "Read tables and series by full scope"
> "Lock the exact requested category level before extraction"

v8 is *bigger* (392 vs 270 lines) but more abstract. SG packs concrete
domain-specific decision rules ("gross debt vs interest-bearing debt") inline,
which the executor can match to the question. v8 emits structural categories
that the executor must interpret onto the document.

**This is the same mechanism documented in
`project_g2b_mechanism_finding_process_vs_function_level`** — v8's K-rollout
group dispatch produces process-level abstractions; SG's K=1 contrastive
produces function-level specifics. On OfficeQA, where every question hinges on
"is this Treasury Bulletin row the right one", **function-level specificity
dominates**.

## v8 regressions from seed (10 tasks)

In 10 cases, the seed (no skill) got it right but v8 (with trained skill) got
it wrong. Of those, SG also got 7/10 right — so v8's training **specifically
damaged** competence on tasks where SG either preserved or improved.

Examples of v8 regressions (seed=PASS, v8=FAIL):
- **oqa-40** (population stdev of CY1981 monthly net outlays): seed got
  6379.29 exactly; v8 got 5560.92 — different period selection induced by
  v8's "audit coverage explicitly" rule pushing toward different aggregation.
- **oqa-58** (R-square 1991-2010): seed got 0.8298 exactly; v8 got 0.8170 —
  small period or formula deviation.
- **oqa-126** (mid-point normalized difference): seed got 0.03; v8 got 2.98
  — formula selection error (same as SG's).

The pattern: v8's skill **adds reasoning steps that misdirect the agent on
tasks the model could solve directly**.

## 4.1 cross-tab — different competencies

At GPT-4.1 (baseline 0%, SG 1%, v8 4%), v8 and SG learned **non-overlapping**
sets of capabilities:

- v8 passes: oqa-1, oqa-2, oqa-5, oqa-125 (4 tasks)
- SG passes: oqa-4 (1 task)
- Overlap: ∅

Each method picked up a different sliver. With baselines this close to floor,
4 vs 1 isn't a meaningful comparison — both essentially can't do OfficeQA at
4.1 (consistent with the OfficeQA-on-weak-backbone floor effect).

## Implications

1. **OfficeQA is a function-level bench.** v8's process-level skill style
   loses 4pp net on 5.4 (within single-seed noise, but the underlying failure
   pattern is non-random). On weak backbone (4.1), neither method works at
   meaningful scale.

2. **v8's gain is bench-modality dependent.** The paper-grade SS/WTQ result
   (+6.7pp / +9.7pp on 4.1) shouldn't be generalized as "v8 helps on weak
   backbone in general". On benches that need precision formula/row selection,
   v8 may be flat or negative.

3. **Anti-wipe doesn't address this.** Anti-wipe correctly catches wholesale
   rewrites (Tier 0 finding); but the *content style* of v8's skill is
   process-level by design (K-rollout group dispatch finds patterns across
   rollouts → abstracts them). Adding more anti-wipe variants won't make v8
   write SG-style function-level rules.

4. **OfficeQA at 4.1 has a floor problem.** 0% baseline → most training signal
   is noise. Multi-seed expansion on OfficeQA-4.1 will likely show large
   variance and small absolute numbers. Probably not worth pushing.

## What this changes about Direction D

If the plan was "multi-seed validate GRPO+anti-wipe on SearchQA / LiveMath /
OfficeQA at 4.1 to upgrade paper from 2-bench to 4-bench":

- **OfficeQA-4.1**: floor effect + format/function-level mismatch — drop from
  multi-seed plan.
- **SearchQA-4.1** (15% baseline): mid-headroom; question type is short-answer
  extraction, more process-friendly than OfficeQA. May still show v8 gain.
- **LiveMath-4.1** (4% baseline): also floor problem; math is function-heavy
  (specific formulas). Risk similar to OfficeQA.

Refined D:
- **D-narrow**: SearchQA-4.1 only, multi-seed (cheap, ~$50-100, 1-2h). Best
  candidate for v8-replicable gain on a 3rd bench.
- Drop OfficeQA / LiveMath at 4.1 unless we want to *report negative results
  as part of the paper* (which actually makes the bench-modality claim
  stronger — "v8 helps on tabular-process benches, doesn't help on
  function-formula benches").

## What this does NOT change

- **SS/WTQ-4.1 paper-grade result stands** ([[project-g2b-final-paper-grade-2026-06-19]]).
- **5.4 saturation finding stands** (4 nulls + this OfficeQA result).
- **Anti-wipe usefulness stands** (Tier 0 confirmed).
