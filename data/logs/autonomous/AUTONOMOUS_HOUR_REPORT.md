# Autonomous Hour Report (12:54 ~ 13:55)

**User absence**: 1 hour autonomous推进 per "根据 badcase 改进 + Tuning 3"

## What was done

### 1. Pre-registration Tuning 3 (12:54)
- `results/sanity_adherence/PRE_REGISTRATION_TUNING3.md` locked
  (md5=f32db6a0a873901236fa62f73721a4ff)
- Pass criteria: A5+T3 vs A0 seed 1 →
  - PRIMARY: Δ≥+2pp + max-min≤6pp + same direction (all 3)
  - ESCAPE: Δ +0.5~+2pp + max-min≤6pp + same direction
  - FAIL: → SAPR archive as negative result, cap optimization 升 P0
- No relax post-hoc; same discipline as sanity Round 2 pre-reg.

### 2. Tuning 3 implementation (12:55-13:00)
- `pipeline/group_adherence_judge.py`:
  - new function `_rule_birth_iters(skill_dir, current_iter)` walks
    snapshot_iter_1..N to record first appearance of each rule heading
  - filter in `run_group_adherence_judge`: skip rules with
    `birth > current_iter - 2` (i.e. < 2 iter old)
  - logs `[SAPR-T3] rule-age filter: skipped N/total young rules`
- Smoke 2-iter verified pipeline integration:
  - iter 1: skipped 6/6 (all rules young, expected)
  - patcher_final_message generated correctly with empty-flag adherence summary

### 3. Train launch (13:01)
- A5+T3 seed 1, 8 iter, 32 task, K=4 via OpenRouter gpt-4.1
- pid 97395 background
- ETA 14:30-15:00 (~1.5-2h)

### 4. Eval monitor staged (13:05)
- `scripts/autonomous_sapr_t3_monitor.sh` pid 97541
- Auto-launches 3 reruns post-train, aggregates verdict per pre-reg
- Output: `logs/autonomous/sapr_t3_results.md`

## Findings during the hour

### Finding: Fix V cap = 150 evidence is correlational, not experimental

Memory `project_g2b_fix_v_architecture` cites: "Empirical observation:
SKILL.md > 150 lines correlates with executor LLM tool-format breaks."
But this was from Fix U seed-level correlation (seed 0 → 133L → 45%;
seed 1 → 164L → 37%; seed 2 → 139L → 32%).

**The 150-line cap was never experimentally validated.** Cap could be
175 or 200 without measurable inference perf loss.

### Implication: cap optimization is a legitimate separate paper line

If we run controlled cap-comparison experiments (cap=150 vs 175 vs 200
vs no-cap), the result could be the second flagship contribution beyond
SAPR's sub-module status.

**Pre-reg experiment design (not yet run)**:
- Fixed: A0 vanilla v8, seed 1
- Variable: cap setting (4 levels)
- Metric: heldout pass rate, training iter revert rate, inference time
  per task
- Acceptance: cap=X gives ≥+2pp over cap=150 AND no inference perf
  degradation → cap reset to X

Total cost: ~$40, ~6h (4 trains × 30min × 3 reruns) — feasible after
T3 verdict.

## Remaining time (~30 min)

Will use to:
1. Read 1 paired badcase trace from A0 vs A5 seed 1 r3 (the -4pp
   rerun where SAPR underperformed) to understand specific failure
2. Check if cap revert pattern is correlated with specific batch
   characteristics (size of pre-patch skill, batch difficulty)

### Deep finding (badcase analysis on seed 1 r3 A5 losses)

Sampled 4 tasks where A5 lost (A0 passed): 46240, 38823, 50768, 55468.
**Pattern: A5 systematically writes formulas that don't evaluate.**

| Task | A5 error | type |
|------|---------|------|
| 46240 | `ws[f'J{row}'] = '=IF(H{row}...)'` 字面 `{row}` 未 f-string 替换 | Python f-string bug |
| 38823 | #VALUE! errors | Excel formula syntax |
| 55468 | INDEX/MATCH 返回 #VALUE! | Excel formula error |
| 50768 | missing cells (partial) | incomplete write |

A0 (vanilla v8) approach on same tasks: writes Python that COMPUTES the
literal value then writes the literal → robust, no formula evaluation
risk.

### Mechanism source: A0 vs A5 L3 chapter divergence

A0 final 7 L3:
- anchor-cell-scanning, avoid-sign-inversion, conditional-formula-blank,
  date-format-joining-with-filter, prefix-stripping-pattern,
  seven_day_window, skip-output-when-source-blank

A5 final 7 L3:
- avoid-invalid-weekday-format-in-text-formula,
  clear-deleted-and-inserted-row-cells, delete-row-if-all-F-L-cells-blank,
  ensure-correct-column-subtraction-after-lookup,
  group-by-min-extraction-and-mapping, iterate-over-all-site-rows,
  sequential-index-to-category-bucket-mapping

A0 L3 = "HOW to compute in Python" style. A5 L3 = "WHEN to use specific
formula (TEXT/INDEX-MATCH) and how" style.

The SKILL.md "Writing Excel Formulas" L2 section is IDENTICAL between
A0 and A5. But the L3 references bias differs through cumulative iter
divergence. This is a concrete instance of the path-dependent mechanism
documented in [[g2b-sapr-mechanism-shape-and-cap-dominance]].

### Tuning 4 candidate (not implemented, for discussion)

**Goal**: reduce A5's formula-writing failure rate without abandoning
SAPR's "polish" advantage on complex tasks like 120-24.

**Idea**: when patcher adds a new rule/L3 about formula usage, also
add a "robustness check" reminder (Python f-string substitution syntax,
post-write evaluation verification).

This is a Tuning 4 candidate after T3 verdict; not for this autonomous
hour.

## State on user return (~13:55)

- Tuning 3 train running, ~50% done
- Eval monitor staged
- This report at `logs/autonomous/AUTONOMOUS_HOUR_REPORT.md`
- No decisions taken beyond Tuning 3 (per "复杂的商讨" rule)

## Open questions for user

1. After T3 verdict (~15:00): if PRIMARY PASS, do we invest in cap
   optimization as 2nd paper line, or focus on writing SAPR sub-module?
2. If T3 FAIL: archive SAPR + cap optimization as new flagship, or
   pivot MBCT?
3. EmbodiSkill collision means SAPR ceiling is auxiliary regardless.
   Is the path-dependent mechanism worth a sub-section in paper, or
   skip entirely?
