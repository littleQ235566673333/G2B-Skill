# C-Topology Negative-Rule Ablation v3 — Placement × Style Disentangle

**Date pre-registered**: 2026-06-21 (post-v2 night run)
**Author**: Claude (offline, pre-commit; not modified after eval starts)
**Supersedes**: nothing — this is a sub-question of v2's negative result

## Why a v3

v2 verdict: outcome null + 5/10 rule_ignored. Two competing mechanisms
explain rule_ignored:
- ① **attention dilution** (rule at line ~395 of 408 → low surface rate)
- ③ **style/integration conflict** (function-level rule fights v8's
  process-level skill content)
- ⑤ **anchoring missing** (bare imperative vs Why-grounded prompt-eng convention)

Improving group_patcher to produce process/function-sectioned skill +
anchored negative rules is **2 days work + $200 retrain**. Before that
spend, run a **$25 / 2h cheap ablation** that disentangles ①/③/⑤ and
tells us which (if any) is fixable at the SKILL.md-level.

## Question

For the 10 v2 negative rules tested on stable-v8-fail OQA-5.4 cases:
**which of placement / style / anchoring drives rule_ignored?**

## Case selection (frozen pre-eval)

5 cases mixing v2's rule_executed and rule_ignored verdicts to detect
both "lift" and "regression" directions:

| case | v2 verdict | rule | category |
|---|---|---|---|
| oqa-112 | rule_ignored | R1 (ratio direction) | aggregate |
| oqa-118 | rule_ignored | R5 (multi-step enumeration) | growth_rate |
| oqa-130 | rule_ignored | R8 (currency conversion) | comparison |
| oqa-14 | rule_executed | R2 (revised data) | comparison |
| oqa-35 | rule_executed | R6 (reporting structure) | lookup |

3 ignored + 2 executed. Reasoning: pure-ignored sample only detects
"upward movement"; pure-executed only detects "regression"; mixed lets
us see both directions.

**Frozen** — no swap-in / swap-out after eval starts.

## Ablation P (placement)

Same 5 rules content (no change). Three placements:

- **Pa** (control = v2 status quo): rules appended at END of v8 SKILL.md, under standalone `## Negative function rules` H2 (line ~395 of 408)
- **Pb** (middle, integrated section): rules inserted as `## Function Rules` H2 between v8's existing "Strategy that works well" and "Common Pitfalls" sections (~line 200)
- **Pc** (top, prominent): rules inserted as `## Critical Avoidances (read first)` H2 right after YAML frontmatter (~line 5)

Rule text identical across Pa/Pb/Pc — only position differs.

## Ablation S (style / anchoring)

Same 5 rules at the same placement (= Pa, end position, to keep P factor controlled).
Three style variants:

- **Sa** (control = v2 status quo): bare imperative
  > Example R1: "When computing means of yearly ratios, compute each year's ratio first, THEN average — do not aggregate sums of A and B first and divide."

- **Sb** (anchored with generalized "Why:"): same rule + brief causal framing
  > Example R1: "When computing means of yearly ratios, compute each year's ratio first, THEN average — do not aggregate sums of A and B first and divide. **Why:** aggregating before averaging produces a weighted mean that depends on the magnitude of A and B, not the per-period ratios; in financial questions this systematically inflates or deflates the result."

  Generalized framing only — NO real case_id / group reference (would require querying training logs, scope creep).

- **Sc** (process-style embedded): rule recast as positive process step in v8's "Strategy" voice
  > Example R1: "Before computing a ratio statistic over multiple periods, restate the numerator and denominator from the question in words. Compute each period's ratio independently, then aggregate. State the formula in pseudocode before executing."

  Imperative "avoid X" → process directive "do Y first". Matches v8 trained skill's "Strategy that works well" style.

Rule text content (the underlying knowledge) is the same across Sa/Sb/Sc.

## Eval design

Each ablation: 5 cases × 3 conditions × 1 seed = 15 runs.
Total: 30 runs ≈ $15–25.

**Per-rule pass_pattern grep** preserved from v2 (heuristic regex for
trace-level avoid signal). Plus outcome pass/fail.

## Pre-committed verdict matrix

Two-axis (avoid_signal_count, outcome_pass_count) per condition.

### Ablation P

| condition | result | interpretation |
|---|---|---|
| Pa: 1-2 / 5 avoid (= v2 baseline) | (control) | — |
| Pc avoid ≥ Pa + 2 OR Pb avoid ≥ Pa + 2 | placement matters | ① is real; **patcher fix = move negative rules to top/middle** |
| Pa ≈ Pb ≈ Pc (within ±1) | placement doesn't matter | ① is NOT primary; rule out attention dilution |

### Ablation S

| condition | result | interpretation |
|---|---|---|
| Sa: 1-2 / 5 avoid (= v2 baseline) | (control) | — |
| Sb avoid ≥ Sa + 2 | anchoring matters | ⑤ is real; **patcher fix = generate Why-anchored rules** |
| Sc avoid ≥ Sa + 2 | process-style framing matters | ③ is real; **patcher fix = generate process-voice negative rules** |
| Sa ≈ Sb ≈ Sc (within ±1) | style doesn't matter | ③/⑤ are NOT primary |

### Combined verdict

| P movement | S movement | verdict |
|---|---|---|
| yes | no | **① primary** — placement dominates; group_patcher placement fix |
| no | yes (Sb) | **⑤ primary** — anchoring dominates; group_patcher Why-template |
| no | yes (Sc) | **③ primary** — style dominates; group_patcher process-voice generation |
| yes | yes | both contribute; group_patcher needs combined fix |
| **no** | **no** | **SKILL.md injection structurally bounded** — no patcher fix recovers; C-topology firmly future work |

The "no/no" cell is the key falsification. If it triggers, the v2 outcome null
generalizes to "any SKILL.md-edit cannot fix OQA-5.4 stable-v8-fail" — paper
finding becomes "post-training skill injection has structural limit at this
scope".

### Multi-seed follow-up

If any condition wins (≥ +2 avoid lift over baseline), re-run that single
condition × 5 cases × 3 seeds (= 15 runs, ~$8) to confirm not single-seed
noise. ONE follow-up only — pre-committed cell, no shopping.

## Budget

- Ablation P: 15 runs ≈ $8
- Ablation S: 15 runs ≈ $8
- Multi-seed follow-up: 15 runs ≈ $8 (only if a condition wins)
- **Total**: $16-24, hard cap **$30**

## What's frozen at this commit

- 5 case selection (3 ignored + 2 executed) — no swap
- 3 placements (Pa/Pb/Pc) and exact insertion points
- 3 style variants (Sa/Sb/Sc) and rule of "no real case_id in Sb"
- Verdict thresholds (≥ +2 avoid lift = real signal)
- Multi-seed follow-up: max 1 condition only
- Hard budget cap $30

## What's NOT in scope

- Changing rule content (knowledge stays same across all conditions)
- Changing the 10 v2 rules' base text (we only restyle 5 of them, others left out)
- Patcher / training-time changes (this ablation is post-training only)
- Multi-bench (OQA-5.4 only)
- The "real case_id" anchored Sb variant (deferred to future test if Sb wins)

## Files

- `analysis/c_topo_ablation/protocol_v3_placement_style.md` — this file
- `analysis/c_topo_ablation/v3_skills/{Pa,Pb,Pc,Sa,Sb,Sc}/` — 6 skill variants
- `analysis/c_topo_ablation/v3_results/` — per-(condition, case) outputs
- `analysis/c_topo_ablation/REPORT_v3.md` — final tally + verdict
