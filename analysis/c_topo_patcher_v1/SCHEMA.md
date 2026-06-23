# Function-Rule Patcher Schema — Section 1: Constraints + Pipeline Map

**Status**: DRAFT, Section 1 only. Sections 2 (field schema) + 3 (Q1-Q4 decisions) pending review of this section first.
**Date**: 2026-06-21
**Goal**: define what changes in `group_diagnoser → momentum → group_patcher` to support Process-Anchored Function Rules, without repeating v3's failure modes.

---

## 1.1 Constraints We Must Respect

These are derived from v1, v2, v3 ablation evidence + v8 implementation history. Any schema decision violating a constraint is auto-rejected. **Read this section first; if a later section conflicts, this section wins.**

### C1. Surface exposure is not enough.
v3 Pb/Pc showed +2x rule mention frequency in trace, but outcome stayed flat. Increasing visible function-style text does not necessarily improve executor outcomes. Any design whose only mechanism is "make the rule more visible" is rejected.

### C2. Function rules must be anchored to execution context.
A function rule should appear near the process step where it is needed, not only in a distant standalone section. Standalone `## Function Rules` H2 at end of SKILL.md is rejected as default placement (allowed only as fallback when no process anchor fits).

### C3. Function rules must remain function-style.
Inline placement must not turn rules into generic process advice. Every function rule must include `applies_when / avoid / use_instead`, with a machine-checkable marker (`<!-- F: avoid -->` HTML comment) that allows post-hoc grep audit.

### C4. Single-task all-fail evidence cannot directly update core skill.
K-rollout uniformity within one task is not cross-task corroboration. `final_answer_uniformity == True` may signal "K rollouts died the same way" but does not signal "this failure mode generalizes". Direct promotion from K-internal uniformity is rejected.

### C5. Function rule promotion requires cross-task corroboration.
- **Strongest**: mixed-group contrastive support (high/low advantage split agrees with the rule).
- **Acceptable**: ≥ 2 distinct task_ids with same-direction `applies_when` failure trace (text similarity ≥ 0.5 token Jaccard on `applies_when` field).
- **Insufficient**: single-task evidence, even if K-uniform.

### C6. Function rules must be reusable operation primitives, not case memory.
Rules containing dataset-specific literals — sheet names, cell addresses (e.g., `A1`), column letters (e.g., `Column B`), file extensions (`.xlsx`), task IDs (`oqa-\d+`), 4+ digit numbers (likely years / answer values), or quoted prose from source documents — cannot enter core. Enforcement is deterministic post-hoc grep, not LLM self-judgment.

### C7. Worked examples define form, not content.
Generated rules must not copy the surface domain of worked examples unless the current evidence independently supports that domain. Patcher prompt §5 (Forbidden) must explicitly list the worked-example domains and forbid replication.

### C8. Schema enforcement must be deterministic where possible.
Field presence checks, literal grep, cross-task matching, marker validation are runner-side code, not LLM self-judgment. LLM judgment is reserved for content quality (rule wording, generalization claim, anchor selection). Rationale: v8 history shows ≥ 5 cases of LLM self-check failure (routing_decisions miss-emit, pending duplicates, generic-violation L2 content). Constraint enforcement that depends on LLM honesty has historically failed.

---

## 1.2 Pipeline Map: Three-Stage Field Flow

The schema change touches three pipeline stages. Naming the responsibilities upfront prevents the v3 failure mode where one component implements its part but upstream/downstream don't supply / consume the data.

```
┌────────────────────────────────────────────────────────────────────────┐
│  STAGE A: pipeline/group_diagnoser.py  +  prompts/group_diagnoser.py   │
│  (Phase 2 — per-group card emission)                                   │
└────────────────────────────────────────────────────────────────────────┘
        │
        │  Per-group card YAML emits new fields (all_fail branch only):
        │    - diagnosis_label: CONVERGENT_ALL_FAIL | DIVERGENT_ALL_FAIL | OTHER
        │    - candidate_claims[].kind: process | function   (NEW)
        │    - candidate_claims[].actionable_function_delta:  (NEW, when kind=function)
        │        applies_when: <≤30 words, generic trigger>
        │        avoid:        <what NOT to do>
        │        use_instead:  <what to do instead>
        │
        │  Hard validation (`_validate_card`):
        │    - kind=function → actionable_function_delta MUST have
        │      all 3 sub-fields non-empty
        │    - applies_when MUST pass deterministic literal_check
        │      (no 4+digit numbers, no file extensions, no task-id patterns,
        │      no Excel-cell patterns)
        │    - all_fail branch: kind=function only allowed when
        │      diagnosis_label == CONVERGENT_ALL_FAIL
        │
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│  STAGE B: pipeline/momentum.py  +  prompts/momentum.py                 │
│  (Phase 3 — pattern record across iterations)                          │
└────────────────────────────────────────────────────────────────────────┘
        │
        │  Pattern record carries forward:
        │    - kind: process | function   (transparent passthrough)
        │    - applies_when                (passthrough)
        │    - avoid / use_instead         (passthrough)
        │    - cross_task_corroboration:  (NEW, recomputed each iter)
        │        same_applies_when_tasks: [task_id, ...]
        │        contradicting_success_tasks: [task_id, ...]
        │
        │  Cross-task matching (deterministic):
        │    - For each function-kind pattern, find other patterns/groups
        │      with applies_when token-Jaccard ≥ 0.5 across distinct task_ids
        │    - Populate same_applies_when_tasks
        │    - Populate contradicting_success_tasks from all_success groups
        │      whose trace matches applies_when context
        │
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│  STAGE C: pipeline/group_patcher.py  +  prompts/group_patcher.py       │
│  (Phase 4 — routing + SKILL.md edits)                                  │
└────────────────────────────────────────────────────────────────────────┘
        │
        │  deterministic_prefilter() reads kind=function patterns and
        │  routes by cross_task_corroboration:
        │    - len(same_applies_when_tasks) ≥ 2
        │      AND len(contradicting_success_tasks) == 0
        │      AND literal_check passes
        │      → core_function (route to Process-Anchored placement)
        │
        │    - else → function_holding (append to pending_pool.md
        │      under "## Function rule candidates" sub-H2)
        │
        │  Patcher LLM responsibilities (route=core_function):
        │    1. Choose target_anchor: existing process H2 id (preferred)
        │       OR "new_function_section" (fallback only when no fit)
        │    2. Emit Process-Anchored bullet block:
        │
        │         <!-- F: avoid -->
        │         - Applies when: <verbatim from applies_when field>
        │         - Avoid: <verbatim from avoid field>
        │         - Use instead: <verbatim from use_instead field>
        │
        │    3. Bullet block inserted at END of chosen process H2,
        │       BEFORE the next H2 boundary
        │    4. Cap: ≤ 2 core_function rules per iter (avoid drowning
        │       process voice)
        │
        │  Post-edit deterministic checks (runner-side, after LLM emits):
        │    - Every <!-- F: avoid --> block must have all 3 bullets
        │    - applies_when field re-grepped for literal violations
        │    - Marker count ≤ 2 added per iter
        │    - On violation: revert that section, log to violations.md
        │
        ▼
   SKILL.md      pending_pool.md     routing_decisions.md
   (process H2s   ("## Function       (new column: kind,
    with embedded  rule candidates"   target_anchor,
    F: blocks)    sub-section)        corroboration_count)
```

---

## 1.3 What Each Stage Owns vs. Does Not Own

| Concern | Stage A (diagnoser) | Stage B (momentum) | Stage C (patcher) |
|---|---|---|---|
| Decide kind: process vs function | **OWN** (LLM, in-prompt) | passthrough | passthrough |
| Emit `actionable_function_delta` | **OWN** | passthrough | consume |
| Validate field presence | **OWN** (`_validate_card`) | re-validate | consume |
| Literal check on `applies_when` | first pass | recheck | **final gate** |
| Cross-task matching | n/a | **OWN** (deterministic) | consume |
| Routing decision | n/a | n/a | **OWN** (deterministic prefilter) |
| Anchor selection | n/a | n/a | **OWN** (LLM, with constraints) |
| Marker enforcement | n/a | n/a | **OWN** (deterministic post-edit) |
| `<= 2 per iter` cap | n/a | n/a | **OWN** (deterministic post-edit) |

---

## 1.4 What This Section Does NOT Cover

Deferred to Section 2 (field schema) + Section 3 (Q1-Q4 decisions):

- Exact YAML schema for new fields (types, required/optional, default values)
- Prompt-side language for diagnoser teaching the kind=process vs kind=function distinction
- Worked example F1 / F2 final wording
- Pending-pool sub-section format details
- Patcher prompt §3a/§3b new rows for `core_function`

Deferred to Step 1 (implementation) of the parent plan:

- Code diff in `group_diagnoser.py` `_validate_card`
- Code diff in `group_patcher.py` `deterministic_prefilter`
- Pilot run config (3 iter, OQA-4.1)
- Post-pilot verification checklist

---

## 1.5 Open Questions for User Review (block Section 2 until answered)

1. **Token-Jaccard threshold for cross-task matching (0.5)** — pulled from intuition, not data. Should I instead pilot 3 thresholds {0.3, 0.5, 0.7} on existing v8 momentum logs to pick empirically? Cost ≈ $0 (offline replay).

2. **Cap "≤ 2 core_function rules per iter"** — chosen to protect process voice. Too tight? Alternative: cap at `min(2, n_process_promotions_this_iter)` so function never exceeds process. Or no cap, rely on `cross_task_corroboration` filter naturally limiting. Preference?

3. **CONVERGENT vs DIVERGENT all_fail labeling** — diagnoser already has logic for this informally; do we want to formalize the criterion (e.g., "K rollouts share the same `cell_comparison` cluster") or leave it LLM-judgment with explicit prompt guidance?

4. **Worked example F1/F2 wording from GPT's draft** — copy as-is or rewrite? GPT's F1 (statistical function selection) is dangerously close to v3 R4 (oqa-40 pstdev), might bias patcher toward stats domain. Suggest rewriting F1 to a different domain (e.g., "field selection from structured records").

---

End of Section 1.
