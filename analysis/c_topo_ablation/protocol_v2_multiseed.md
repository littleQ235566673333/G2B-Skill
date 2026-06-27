# C-Topology Negative-Rule Ablation v2 — Multi-Seed Pre-Registered Protocol

**Date pre-registered**: 2026-06-21
**Author**: Claude (offline, pre-commit; not modified after eval starts)
**Supersedes**: `protocol.md` (v1) on the outcome layer; v1 behavior-layer
result (4/5 v8+neg vs 1/5 v8 avoid_signal) is preserved as-is.

## Why a v2

v1 outcome layer is invalid: case selection assumed v8 fails on the 5 OQA
cases under single seed; in re-run v8 itself passes 3/5, so the
"v8 must fail" baseline is broken. v1 behavior layer (grep avoid_signal)
is unaffected and stands as a separate finding.

v2 isolates **outcome lift** with a stable case pool and multi-seed eval.
Behavior layer is not re-run.

## Question

Does adding tailored negative function rules to v8's SKILL.md produce a
**measurable outcome-pass rate lift** on a v8-stable-fail case pool, under
multi-seed eval?

Necessary, NOT sufficient: positive result = "tailored rules can lift
outcome when capability headroom exists"; does NOT validate
diagnoser-derived rules or end-to-end C-topology training.

## Case selection (executed BEFORE looking at any v8+neg outcome data)

Pool source: OQA-5.4 eval set (same as v1).

### Multi-seed v8 stability filter — pilot-then-branch design

**Definitions** (frozen):
- `v8_stable_fail` := v8 passes ≤ 1 / 5 seeds
- `v8_stable_pass` := v8 passes ≥ 4 / 5 seeds
- `N` floor for main eval = **8** (relaxed from 10; paired-bootstrap CI half-width inflates by ~12% at N=8 vs N=10, acceptable for outcome direction; flagged in REPORT)

### Stage P (Pilot): cheap probe of v1 candidate stability

Pilot pool = 6 OQA-5.4 cases passing v1's strict rules
(rel_err > 0.10 AND SG predicted == gold exact AND ≠ oqa-51):
**oqa-14, oqa-16, oqa-25, oqa-33, oqa-40, oqa-129**.

Run v8 on each pilot case × 5 seeds (executor-level seeds). Count
per-case pass rate.

Cost: 30 runs ≈ $21.

### Branch decision (frozen, applied as soon as pilot finishes)

| pilot stable_fail count (n_sf) | branch | action |
|---|---|---|
| n_sf ≥ 5 / 6 | **Branch 1: small expand** | Add 3 SG-exact remaining v1-lost cases (oqa-58, oqa-91, oqa-112; rel_err < 0.10 but SG nailed). Run 5 seeds on new 3. If total stable_fail ≥ 8 → main eval. Else cascade to Branch 3. |
| 2 ≤ n_sf ≤ 4 | **Branch 2: SG-exact extension** | Same action as Branch 1 (add the 3 SG-exact cases). Same cascade rule. (Branch 1 vs 2 differ only in expectation; the action is identical because Branch 2's no-rel_err-filter would still leave us at the 9-SG-exact superset, and SG-not-exact cases violate rule provenance.) |
| n_sf ≤ 1 | **Branch 3: random 30 v8-fail** | Skip SG-exact path. Pool = all v8-failed cases on the 100-task heldout (51 cases), excluding oqa-51. Sort by `tid` ascending; take **first 30**. Frozen sample, no random call. Run 5 seeds on each. SG-fail rules will need `provenance=question_only` tag for sensitivity analysis (see verdict matrix). |

**Cascade rule (Branch 1 / 2 → 3, frozen)**: If after Branch 1 or 2's
small expansion the total stable_fail count is still < 8, automatically
cascade to Branch 3 protocol. Combined budget cap stays at $200; if cap
hit before Branch 3 completes, halt and report partial.

**Branch 3 random sample lock**: Use `sorted([tid for tid in v8_fail_set
if tid != "oqa-51"])[:30]`. No randomness, no resampling. The same
deterministic list is reproducible from the v8 eval_summary.json.

### Halt condition (frozen, pre-eval)

If after pilot + chosen branch + cascade the total `v8_stable_fail` pool
is **< 8 cases**, halt main eval. Do NOT relax stable_fail definition
(≤ 2/5 would defeat the test premise). Report as standalone finding:
"v8 baseline on OQA-5.4 v8-lost candidates is not reproducibly failing
under multi-seed; the v1-lost cases and a 30-case random v8-fail sample
are largely seed-noise artifacts, not stable capability gaps. Outcome
lift hypothesis cannot be tested in this pool." This itself is a
paper-grade negative finding about v8's single-seed result reliability.

**Frozen once selected.** No swap-in / swap-out after v8+neg runs start.

## Rule provenance

For each selected case, write **one tailored negative rule** following v1
style (observed-failure-mode → "avoid X / instead Y" sentence). Same
"best-case tailored rule" framing — diagnoser-generalization is a
separate question, out of scope here.

Rule writing must happen BEFORE any v8+neg eval. Rules frozen at commit.

## Eval design

Conditions: `v8` (control), `v8_plus_neg` (treatment). Same skill except
`v8_plus_neg` has the N appended negative rules.

Per case × per condition: **5 seeds**. Outcome = pass/fail per seed.

## Primary metric & decision rule

Per case `i`, let `p_i^v8` = v8 pass count / 5, `p_i^neg` = v8+neg pass
count / 5. Per-case delta `Δ_i = p_i^neg − p_i^v8`.

Aggregate (all reported, not optional):
- **mean(Δ)** + 95% CI via paired bootstrap, 10000 resamples
- **median(Δ)** as robustness check (less sensitive to 1-2 outlier cases)
- **per-case Δ distribution** (histogram + count of positive / zero / negative)

Pre-committed verdict matrix (applied in order; first match wins):

| condition | verdict |
|---|---|
| 95% CI lower > 0 **AND** median Δ > 0 **AND** positive-Δ case count ≥ N/2 (≥5/10) | **C-topology promoted to paper main contribution.** Mechanism + outcome both confirmed. |
| 95% CI lower > 0 but **median Δ ≤ 0** OR **positive-Δ count < N/2** | **inconclusive (concentration flag).** Mean lifted by 1-2 cases; demote to "future work, requires broader validation". |
| 95% CI lower ≤ 0 **AND** 95% CI upper > 0 | **inconclusive.** Behavior-layer finding (v1 4/5 vs 1/5) stands standalone; C-topology → "future work" in paper. |
| 95% CI upper ≤ 0 | **C-topology line retired** — pending negative-verdict qualitative below. |

### Negative-verdict qualitative (mandatory, pre-committed criteria)

Triggered when 95% CI upper ≤ 0. For all N cases in `v8_plus_neg` runs,
grep the rule's `avoid_check.pass_signal` in the executor trace
(same heuristic style as v1):

- **rule_executed** count = cases where pass_signal grep hits in ≥ 3 / 5 seeds
- **rule_ignored** count = cases where pass_signal grep hits in ≤ 1 / 5 seeds

Confound-resolution table (frozen):

| rule_executed | rule_ignored | interpretation |
|---|---|---|
| ≥ 7/10 | ≤ 2/10 | **capability ceiling.** Rules followed but model still wrong → C-topology mechanism intact, OQA capability bound. Paper case study, do not retire mechanism. |
| ≤ 3/10 | ≥ 6/10 | **rule-following failure.** Executor ignores SKILL.md negative rules → C-topology mechanism broken at executor layer. Retire C-topology line. |
| anything else | | **mixed, unresolvable.** Report as such, do not claim either direction; C-topology → future work. |

This contingent step is committed pre-eval to prevent post-hoc
interpretation freedom.

Secondary checks (informational):
- **Negative-control reuse**: v1's 5 cases (oqa-14/-16/-33/-40/-129)
  re-run shows v8 passes 3/5 of them; reuse those 3 as `v8_stable_pass`
  controls (saves a separate selection round + gives within-case
  v8→v8+neg regression signal). 3 seeds each on v8+neg condition.
  If regression > 1pp absolute on aggregate or any single case drops
  ≥ 2/3 seeds, flag in paper.

- **SG-fail rules sensitivity (only triggered if Branch 3 is taken)**:
  When Branch 3 is used, some main-eval cases will be from the SG-fail
  set (i.e., SG also failed → no clean reference pattern → rule written
  from question + gold only). Tag these cases as
  `provenance=question_only`. Compute `mean Δ_full` (all N cases) and
  `mean Δ_SG_exact_only` (only cases where SG also passed). Frozen
  sensitivity rule:

  | full vs SG-exact-only | interpretation |
  |---|---|
  | mean Δ_SG_exact_only ≥ 0.5 × mean Δ_full **AND** both have CI lower > 0 | Result robust; rules generalize beyond cherry-picked SG-exact reference |
  | mean Δ_SG_exact_only < 0.5 × mean Δ_full | **Driven by question-only rules.** Note in paper: "tailored rule lift requires gold-pattern reference; pure question-wording rules less effective." |
  | SG-exact-only sample < 4 cases | Insufficient subset for sensitivity analysis; report n and CI as caveat |

## Budget

Estimated per-run cost on OQA-5.4: ~$0.7 (v1 empirical: $0.5–1.0 per case
incl. reasoning + long source files).

- Phase A stability filter: ~15 cases × 5 seeds = 75 runs ≈ $53
- Phase B (if triggered): ~10 cases × 5 seeds = 50 runs ≈ $35
- Main eval: 10 cases × 2 conditions × 5 seeds = 100 runs ≈ $70
- Negative-control (reuse v1 cases): 3 cases × 1 condition × 3 seeds = 9 runs ≈ $6
- Expected total: ~$130 (Phase A only) to ~$165 (Phase A+B)

Hard cap: **$200**. If exceeded mid-run, halt and report partial.
Justification for raising from v1's $150: 5-seed filter + 10-case main
eval is the minimum to get reliable paired-bootstrap CI; cutting either
defeats the purpose of v2.

## What's frozen at this commit

- Stability filter definition (≤1/5 → stable_fail, ≥4/5 → stable_pass)
- Case count **N = 10** (not 10–15); reserve cases not used in main analysis
- Two-phase pool construction (Phase A rel_err > 0.10 → Phase B > 0.05 if needed)
- 5 seeds per (case × condition); 5-seed filter preserved
- Aggregate metrics: mean Δ + 95% CI **AND** median Δ **AND** per-case distribution
- 4-tier verdict matrix incl. concentration flag (median + positive-count gate)
- Negative-verdict qualitative grep with frozen 7/10 vs 3/10 thresholds
- Negative-control: reuse v1's 3 cases where v8 re-run passes
- Budget cap **$200**
- "No editing rules / no swapping cases / no re-tuning after eval starts"

## What's NOT in scope (explicit out-of-scope, do not let scope-creep)

- Diagnoser-derived rules (this tests tailored rules only)
- Process rule layer (this tests function rules only — process rules deferred)
- Cross-task generalization (single eval set OQA-5.4)
- End-to-end C-topology training pipeline

## Files

- `analysis/c_topo_ablation/protocol_v2_multiseed.md` — this file
- `analysis/c_topo_ablation/v2_case_pool.json` — stability filter output (TBD)
- `analysis/c_topo_ablation/v2_rules.yaml` — N tailored rules (TBD, frozen pre-eval)
- `analysis/c_topo_ablation/v2_eval_results/` — per-(case, seed, condition)
- `analysis/c_topo_ablation/REPORT_v2.md` — final tally + verdict
