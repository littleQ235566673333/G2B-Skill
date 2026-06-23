# C-Topology Negative-Rule Ablation — Pre-Registered Protocol

**Date pre-registered**: 2026-06-21
**Author**: Claude (offline, pre-commit; not modified after eval starts)

## Question being answered

Does writing **tailored negative rules** into the v8 trained skill measurably
change executor behavior on a held-out set of v8-failure cases? This is a
sanity-check of the C-topology mechanism core hypothesis: that
SKILL.md-level negative function rules can redirect the executor.

**Necessary, NOT sufficient**: a positive result here means "if rules were
perfect, mechanism works"; it does NOT validate end-to-end C-topology
training. A negative result means "even tailored rules don't help — drop
the C-topology line entirely".

## Pre-committed go/no-go matrix

Two dimensions per case:
1. **avoid_signal**: whether the trace shows behavior consistent with the
   rule's guidance (machine-checkable heuristic, defined per-rule below).
2. **outcome_pass**: whether the case passes the bench grader.

Aggregate matrix over 5 cases:

| avoid_signal count | outcome_pass count | verdict |
|---|---|---|
| ≥4/5 | ≥3/5 | **success** — C-topology mechanism core works; proceed to design completion |
| ≥4/5 | 1-2/5 | **marginal** — rules followed but rare wins; need 3 more cases to disambiguate |
| ≥4/5 | 0/5 | **rule_correct_no_lift** — rules followed but capability ceiling. C-topology mechanism intact but cannot save OQA-5.4 — paper limitation case study |
| 3/5 | any | **boundary** — must run 3 case-by-case extra eval rounds (3-seed) to disambiguate; do not commit either way |
| <3/5 | any | **fail** — executor doesn't follow the rules. C-topology mechanism layer broken. **DROP entire C-topology line.** |

Single-seed for cases with clean avoid_signal verdict. For cases on the
outcome boundary (e.g., 3/5 outcome_pass overall), each unclear case gets
3-seed retest. Total budget: <$15.

## Case selection — fixed by these rules (no cherry-picking)

Selection rules pre-committed in prior conversation turn:
1. v8 rel_err > 0.10 (exclude small numeric deviations)
2. SG predicted == gold exact (clean ground truth pattern)
3. Spread across question categories
4. Exclude oqa-51 (sequence answer, rel_err undefined)

Applied → 6 candidates. Drop oqa-25 (Zipf exponent: niche statistical
concept; rule cannot generalize). Final 5:

| tid | category | gold | SG | v8 | rel_err |
|---|---|---|---|---|---|
| oqa-14 | comparison | 142 | 142 ✓ | 489 | 2.44 |
| oqa-16 | extremum + cross-table lookup | 92000000 | 92000000 ✓ | 570000000 | 5.20 |
| oqa-33 | aggregate / specific lookup | 44174 | 44174 ✓ | 34174 | 0.23 |
| oqa-40 | statistical | 6379.29 | 6379.29 ✓ | 5560.92 | 0.13 |
| oqa-129 | comparison + unit conversion | 264.632 | 264.632 ✓ | 986.622 | 2.73 |

## Rule provenance

Rules below are reformatted from observed failure modes in the
`analysis/officeqa_badcase_analysis.md` writeup and the question wording.
**No new analytical content** — only re-cast as imperative
"avoid…/instead…" sentences in the style v8's diagnoser produces on
CONVERGENT all_fail groups.

This is the "best-case tailored rule" scenario: rules are written knowing
the failure. A positive result means tailored rules work; further test
needed for diagnoser-derived rules generalizing to unseen evals.

## Negative rules (one per case)

### Rule R1 — for oqa-14 (comparison, "revised WWII-era figures")

```yaml
- rule_id: R1
  case_id: oqa-14
  text: |
    When the question explicitly requests "revised" or "updated" figures
    from a WWII-era period, do NOT use the contemporaneous bulletin (e.g.,
    1942_10 for 1942 data) as the source for that period's figure. The
    revisions appear only in later bulletins (1947+ for WWII-era data);
    use the latest available bulletin in the source set when "revised" is
    in the prompt.
  avoid_check:
    fail_signal: |
      Trace reads numeric values from a 1942_10.txt-like contemporaneous
      file when computing the 1934 or 1946 PWA / public-works number.
      Detect: trace contains `read("treasury_bulletin_1942_10` AND
      lines mentioning extraction of "public works" / "PWA" from that file.
    pass_signal: |
      Trace reads both 1934 and 1946 figures from `1947_08.txt` (the
      revised post-war bulletin). Detect: trace contains
      `treasury_bulletin_1947_08` AND no extraction of comparable figures
      from `1942_10`.
```

### Rule R2 — for oqa-16 (extremum then cross-table lookup)

```yaml
- rule_id: R2
  case_id: oqa-16
  text: |
    For two-step questions ("find the month X where Y is min/max, then
    look up Z at that month"), explicitly identify and write down the
    extremum-month BEFORE looking up the second value. Avoid jumping to
    the second extraction by keyword alone — the second value must be
    indexed by the chosen month, not by any other heuristic.
  avoid_check:
    fail_signal: |
      Trace extracts railroad-retirement-account receipts from a row whose
      month does NOT match the spread-min month chosen in step 1.
      Detect: trace lacks a sequenced statement of the form
      "spread minimum is at <month/year>" before the receipts extraction.
    pass_signal: |
      Trace contains explicit identification of the chosen month/year for
      yield-spread minimum (text like "minimum at YYYY-MM" or
      "month/year = ...") AND uses that exact month/year as the index for
      the railroad-retirement lookup.
```

### Rule R3 — for oqa-33 (specific report position lookup)

```yaml
- rule_id: R3
  case_id: oqa-33
  text: |
    When the question references a Treasury Office of Foreign Exchange
    Operations net position with a qualifier ("not considering options",
    "excluding swaps", etc.), do NOT compute the net by manual
    subtraction. The bulletin already publishes the qualified subtotal —
    locate the row literally labeled with that qualifier ("Total net
    position excluding options" or similar) and read it directly.
  avoid_check:
    fail_signal: |
      Trace shows manual arithmetic subtracting an "option positions" row
      from a broader "Total net position" row. Detect: trace contains
      arithmetic operations involving option-related row values, OR
      output value differs from the published subtotal by a round number
      that matches a removable component (e.g., off by exactly 10000
      = options row value).
    pass_signal: |
      Trace identifies and reads a single literal row whose label
      already excludes options, with no manual subtraction step.
```

### Rule R4 — for oqa-40 (statistical: population stdev)

```yaml
- rule_id: R4
  case_id: oqa-40
  text: |
    The question explicitly asks for **population** standard deviation.
    Use `statistics.pstdev` or equivalent (divide by N), NOT
    `statistics.stdev` (divides by N-1). Also: "for the months in CY1981"
    means all 12 calendar months of 1981, not fiscal year 1981 and not
    a subset.
  avoid_check:
    fail_signal: |
      Trace uses `statistics.stdev(` (sample) without `pstdev`, OR
      computes over fewer than 12 values, OR computes over fiscal-year
      months (Oct 1980 – Sep 1981) instead of calendar-year (Jan-Dec 1981).
      Detect: grep `statistics.stdev(` (with that exact call) and absence
      of `pstdev`; OR len(values) != 12 in trace; OR explicit FY date
      range.
    pass_signal: |
      Trace contains `pstdev(` call OR equivalent population formula
      `sum(...)/N` with N=12, over the 12 CY1981 months.
```

### Rule R5 — for oqa-129 (multi-step inflation adjustment)

```yaml
- rule_id: R5
  case_id: oqa-129
  text: |
    For BLS CPI-U inflation adjustments, the question specifies the
    base year (e.g., "1982-84=100 base"). Verify the CPI series used
    is the correct BLS CPI-U with that base before computing the ratio.
    Do NOT use a memory-supplied or implicit deflator. State the CPI
    values for each adjustment year in the trace before applying.
  avoid_check:
    fail_signal: |
      Trace performs the inflation adjustment without explicitly stating
      the CPI-U values for FY 1960, FY 1961, FY 1962. Detect: arithmetic
      step `value * <ratio>` appears in trace before any line containing
      both "CPI-U" and three numeric CPI values for the three years.
    pass_signal: |
      Trace explicitly lists CPI-U values for each adjustment year (1960,
      1961, 1962) along with "1982-84=100" or "base" reference, BEFORE
      computing inflation-adjusted debt levels.
```

## Eval setup

```bash
# Step 1: build a "v8 + 5 negative rules" skill
cp -r results/runs/g2b-v8_gpt-5.4_oqa-gpt54-smoke/train/final_skill \
      analysis/c_topo_ablation/skill_v8_plus_neg
# Append negative rules section to SKILL.md (programmatically, see script)

# Step 2: eval the 5 cases on three skill conditions
for skill in seed v8 v8_plus_neg; do
  for tid in oqa-14 oqa-16 oqa-33 oqa-40 oqa-129; do
    eval $skill on $tid (single seed)
  done
done

# Step 3: per-case grep avoid_signal from execution_trace_r0.md
# Step 4: tally outcome_pass from assessment_r0.json
# Step 5: apply pre-registered matrix
```

## What's frozen at this commit

- Selection rules (4 rules above) — frozen
- 5 cases (oqa-14, -16, -33, -40, -129) — frozen
- 5 rule texts + avoid_check signals — frozen (no editing after eval starts)
- Decision matrix — frozen
- "No re-prompting / no re-tuning rules to make it pass" — frozen

If anything changes after eval starts, this is no longer a pre-registered
test and result must be reported as such.

## Files

- `analysis/c_topo_ablation/protocol.md` — this file
- `analysis/c_topo_ablation/rules.yaml` — machine-readable rule specs
- `analysis/c_topo_ablation/skill_v8_plus_neg/` — skill dir for eval
- `analysis/c_topo_ablation/eval_results/` — per-case eval outputs
- `analysis/c_topo_ablation/REPORT.md` — final tally + verdict
