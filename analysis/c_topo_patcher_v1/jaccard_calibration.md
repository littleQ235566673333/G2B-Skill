# Jaccard Threshold Calibration — replay output
**Source**: 4 v8 fix runs, all `batch_diagnoses.md` 1-10 iter
**Diagnose entries loaded**: 60
**Function-rule candidates** (CONVERGENT all_fail, applies_when ≥30 chars): 25
**Cross-task pairs**: 289

## Jaccard distribution (rounded to 0.1)

| Jaccard bin | count |
|---|---|
| 0.1 | 193 |
| 0.2 | 89 |
| 0.3 | 7 |

## Cross-task pair count above each threshold

| threshold | n_pairs | % of total |
|---|---|---|
| ≥ 0.2 | 35 | 12.1% |
| ≥ 0.3 | 2 | 0.7% |
| ≥ 0.4 | 0 | 0.0% |
| ≥ 0.5 | 0 | 0.0% |
| ≥ 0.6 | 0 | 0.0% |
| ≥ 0.7 | 0 | 0.0% |

## FROZEN labeling criterion (DO NOT modify after pair inspection)

> A pair is **`same_trigger`** iff: a single `applies_when` clause (generic, ≤30 words, no dataset literals) could be written that covers BOTH diagnoses' failure conditions. The pair is **`different_trigger`** iff such a unified clause would either be too generic to be actionable, OR would have to enumerate unrelated cases. **`unclear`** is the third option only when the diagnoses are too short / unparseable to judge.

Rule: judge based on the anonymized `applies_when` text alone. Do NOT consult task_id, bench, label, or run id. Do NOT change this criterion after seeing pairs.

## Anonymized sample pairs per band — fill `judgment` column

### Band Jaccard 0.2-0.30

**Pair 1** (J=0.25)

- A applies_when: `CONVERGENT. All 4 rollouts extracted the same Treasury bond bid-price series and applied simple exponential smoothing in essentially the same way, but they all converted the forecast into DEM with the`
- B applies_when: `CONVERGENT. All 4 rollouts made the same core mistake: they pulled the U.S. Treasury value from the wrong table family and then applied the FX ratios to that wrong series. Instead of using the Treasur`
- judgment: `[ ]` same_trigger / `[ ]` different_trigger / `[ ]` unclear

**Pair 2** (J=0.28)

- A applies_when: `CONVERGENT. All 4 rollouts failed to output any answer (empty string or None), but the intermediate traces show similar unsuccessful attempts to compute the annualized realized volatility as requested`
- B applies_when: `CONVERGENT. All 4 rollouts failed to produce any output in the answer cell (empty string), indicating the same failure mode: no computation or formula was written to calculate the Pearson correlation`
- judgment: `[ ]` same_trigger / `[ ]` different_trigger / `[ ]` unclear

**Pair 3** (J=0.21)

- A applies_when: `CONVERGENT. All 4 rollouts failed to produce any output for the cell—each returned an empty string rather than a number. This indicates the agent did not extract or compute the absolute quarter-over-q`
- B applies_when: `CONVERGENT. All 4 rollouts failed to produce any numerical answer, leaving the cell blank. Each rollout attempted to process the question about counting local maxima on line plots in a scanned documen`
- judgment: `[ ]` same_trigger / `[ ]` different_trigger / `[ ]` unclear

**Pair 4** (J=0.25)

- A applies_when: `CONVERGENT. All 4 rollouts failed on the same underlying task: they found the correct table, but misinterpreted how the monthly rows map to years in the wide, repeated-column layout. The table places`
- B applies_when: `CONVERGENT. All 4 rollouts found the same table and the same two monthly totals, but then treated “absolute percent difference” as an absolute dollar difference in millions. Three rollouts computed `a`
- judgment: `[ ]` same_trigger / `[ ]` different_trigger / `[ ]` unclear

**Pair 5** (J=0.20)

- A applies_when: `CONVERGENT. All 4 rollouts treated the task as “look up two monthly totals and compute a percent difference,” but they applied the wrong normalization rule for “absolute percent difference.” Three rol`
- B applies_when: `CONVERGENT. All 4 rollouts misread the nonbanking-firms tables by selecting the wrong office-scope rows before computing the correlation. The task asked for the Belgian-franc positions and Canadian-do`
- judgment: `[ ]` same_trigger / `[ ]` different_trigger / `[ ]` unclear

**Pair 6** (J=0.20)

- A applies_when: `CONVERGENT. All 4 rollouts failed on the same underlying task: they found the correct table, but misinterpreted how the monthly rows map to years in the wide, repeated-column layout. The table places`
- B applies_when: `CONVERGENT. All 4 rollouts treated the task as “look up two monthly totals and compute a percent difference,” but they applied the wrong normalization rule for “absolute percent difference.” Three rol`
- judgment: `[ ]` same_trigger / `[ ]` different_trigger / `[ ]` unclear

**Pair 7** (J=0.26)

- A applies_when: `CONVERGENT. All 4 rollouts extracted the same Treasury bond bid-price series and applied simple exponential smoothing in essentially the same way, but they all converted the forecast into DEM with the`
- B applies_when: `CASE: CONVERGENT. All 4 rollouts correctly extracted the fish quota quantities and correctly computed the forecast-vs-actual percentage gap, but then failed at the same downstream step: they divided b`
- judgment: `[ ]` same_trigger / `[ ]` different_trigger / `[ ]` unclear

**Pair 8** (J=0.20)

- A applies_when: `CONVERGENT. All 4 rollouts successfully found the relevant Treasury Foreign Currency Reporting rows and did the substantive conversion/comparison work, but they failed at the final answer representati`
- B applies_when: `CASE: CONVERGENT. All 4 rollouts correctly extracted the fish quota quantities and correctly computed the forecast-vs-actual percentage gap, but then failed at the same downstream step: they divided b`
- judgment: `[ ]` same_trigger / `[ ]` different_trigger / `[ ]` unclear

**Pair 9** (J=0.26)

- A applies_when: `CONVERGENT. All 4 rollouts failed to produce any output — every execution trace is missing a numerical answer in the designated cell, reflecting a total lack of computation or return value. This is no`
- B applies_when: `CONVERGENT. All 4 rollouts failed to produce any numerical answer, leaving the cell blank. Each rollout attempted to process the question about counting local maxima on line plots in a scanned documen`
- judgment: `[ ]` same_trigger / `[ ]` different_trigger / `[ ]` unclear

**Pair 10** (J=0.21)

- A applies_when: `CONVERGENT. All 4 rollouts found the same table and the same two monthly totals, but then treated “absolute percent difference” as an absolute dollar difference in millions. Three rollouts computed `a`
- B applies_when: `CASE: CONVERGENT. All 4 rollouts successfully found the correct mid-March 2016 rows, used the right exchange-rate directions, and computed the intended difference from the Treasury tables. The shared`
- judgment: `[ ]` same_trigger / `[ ]` different_trigger / `[ ]` unclear


### Band Jaccard 0.3-0.40

**Pair 1** (J=0.31)

- A applies_when: `CONVERGENT. All 4 rollouts failed to produce any output — every execution trace is missing a numerical answer in the designated cell, reflecting a total lack of computation or return value. This is no`
- B applies_when: `CONVERGENT. All 4 rollouts failed to produce any output in the answer cell (empty string), indicating the same failure mode: no computation or formula was written to calculate the Pearson correlation`
- judgment: `[ ]` same_trigger / `[ ]` different_trigger / `[ ]` unclear

**Pair 2** (J=0.31)

- A applies_when: `CONVERGENT. All 4 rollouts found the same table and the same two monthly totals, but then treated “absolute percent difference” as an absolute dollar difference in millions. Three rollouts computed `a`
- B applies_when: `CONVERGENT. All 4 rollouts found the same September 1975 row in Table GA-III-3 and used the same two values — receipts 753 and expenditures other than investments 735 — then all computed the Gini coef`
- judgment: `[ ]` same_trigger / `[ ]` different_trigger / `[ ]` unclear


### Band Jaccard 0.4-0.50

(no pairs in this band)

### Band Jaccard 0.5-0.60

(no pairs in this band)

### Band Jaccard 0.6-0.70

(no pairs in this band)

### Band Jaccard 0.7-1.01

(no pairs in this band)

## Decision protocol (apply AFTER labeling all sample pairs)

Threshold T = lowest value where:
1. precision ≥ 0.7 (≥7/10 sample pairs labeled `same_trigger`)
2. recall not catastrophically low (≥3/10 of band ≥T are `same_trigger`)

If multiple T satisfy, pick the LOWER T (favor recall).
If no T satisfies → fall back to **0.3 default** AND flag in SCHEMA Section 2 as caveat.
