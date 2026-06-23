# Phase 3 — Group-aware momentum (design draft, not implementation)

> Status: design only. Implementation deferred until A10 smoke passes
> and B-layer milestones land.
>
> Key principle: **augment SkillGrad's momentum schema, do not replace
> it**. Preserve pattern record + per-task overlay + workflow-themes
> machinery. Add group metadata so the patcher's quantitative routing
> (Phase 4) has the signals it needs.

---

## 1. Why this isn't a rewrite

SkillGrad's `prompts/momentum.py` (250 lines) already does the
cross-task pattern extraction we need. Specifically:

- pattern record schema (`pattern-id-slug | kind | description`)
- merge-by-default cluster policy
- append-only `remedy_log` per pattern
- per-task overlay block + `## WORKFLOW-THEMES` aggregation

What it lacks for G2B:

1. **No group metadata.** Each overlay entry only knows
   `signal: failure | success` (binary, single-trajectory) — does not
   distinguish a mixed-group within-task contrast from a single
   contrastive-via-base-trajectory entry.
2. **No reward distribution.** Cannot tell a "lucky single success"
   from a "robust pattern that succeeds K-of-K times".
3. **No evidence-strength signal.** Patterns sourced from one all-fail
   group should NOT be promoted to L2 (per the framework's hard
   constraint), but the current schema has no field to carry that
   instruction.

Phase 3 closes these three gaps **only**. Anything else (verification,
contradiction handling, retrieval indexing) stays in Phase 4 / 6.

---

## 2. Schema additions

### 2.1 Per-task overlay (added fields marked `+`)

```
### [<task_id>] <one-line signal description>
- signal: failure | success
- pattern: <pattern-id-slug> | new | no-actionable-signal
- anchor: <kebab-case slug or (none)>
- gap: <free-form prose>
- proposed_change: <free-form prose>
+ group_type: mixed | all_fail | all_success
+ group_reward_distribution: {success: int, fail: int}
+ group_advantage_summary:
+   high_adv_rollouts: [r0, r2]
+   low_adv_rollouts:  [r1, r3]
+   advantages:        [+0.36, -0.24, +0.31, -0.44]   # soft-acc-centered
```

The `signal` field's existing semantics still hold (failure / success
on the binary `is_correct` axis), but `group_type` carries strictly
more information:

- `signal: success` + `group_type: mixed` → at least one rollout passed
  but at least one failed; the within-task contrast is the strongest
  evidence form.
- `signal: success` + `group_type: all_success` → robustly correct;
  feeds the regression coreset rather than producing a claim.
- `signal: failure` + `group_type: all_fail` → all K rollouts failed;
  evidence-weak (could be capability gap, not skill gap).
- `signal: failure` + `group_type: mixed` → contradictory at first
  glance but legal: K rollouts mostly fail, one succeeds; the failure
  description for THIS overlay entry comes from a low-advantage
  rollout. The pattern entry will record the high-advantage rollout
  separately as the contrastive lesson.

### 2.2 Pattern record

Replace SkillGrad's single-field summary with an **evidence_profile**
that records *what kinds of group evidence supported this pattern*,
plus two **derived** strength buckets — one for routing (`current`),
one for audit / explanation (`peak`).

```
### <pattern-id-slug> | <kind> | <description>
- anchor: <slug>
- appeared_in: iter_2, iter_3, iter_5
+ evidence_profile:
+   mixed_support:        int           # # iterations where a mixed group supported this pattern with a clean advantage split
+   all_fail_support:     int           # # iterations where evidence came from an all_fail group only
+   all_success_support:  int           # # iterations where an all_success group corroborated this pattern
+   contradiction_count:  int           # # iterations where evidence contradicted the pattern's stated rule
+   source_groups: [<iter>:<task_id>]   # audit trail of every supporting group
+ last_mixed_iter: int                  # iter id of the most recent mixed-group support; used by Phase 6 freshness checks
+ peak_strength:    high | medium | low  # max strength ever reached (monotonic; audit-only)
+ current_strength: high | medium | low  # strength as of this iter (routing input; can demote — see §6)
- description: ...
- latest_executor_action: ...
- remedy_log:
  - iter_2 | diagnosis: ... | patch: ...
```

**Why profile + peak + current:**

- `evidence_profile` answers "*what evidence stack does this pattern
  rest on?*" — directly auditable, useful for ablation and reviewer
  questions.
- `peak_strength` answers "*has this pattern ever been corroborated
  cleanly?*" — once a pattern earns a `high` peak, that fact is
  preserved. Useful when a pattern's `current_strength` later demotes
  (§6); peak says "we used to trust this, here's the audit".
- `current_strength` is the only field routing reads. It's derived from
  the profile + the demotion rules in §6 so a single rule change
  doesn't require rewriting historical patterns.

**Strength derivation (v1, simple):**

```
current_strength =
    high   if mixed_support ≥ 1 and contradiction_count == 0
    medium if mixed_support == 0 and (all_success_support ≥ 1 OR weak-mixed-only)
    low    if all evidence is all_fail (i.e. mixed_support + all_success_support == 0)

peak_strength = max(peak_strength, current_strength)   # monotonic non-decreasing
```

Demotion of `current_strength` is governed by §6 (downgrade
mechanism), not by `evidence_profile` alone.

### 2.3 Hard constraint encoded into the schema

Patterns with `current_strength: low` (i.e., evidence_profile shows
`mixed_support + all_success_support == 0`) MUST NOT be promoted by
the patcher to SKILL.md (L2). They live in the pending pool / L3
case-memory layer until a mixed group corroborates them.

Two follow-on constraints for `all_success` evidence (encoded in
schema docstring; enforced in code):

1. an all_success-only pattern can update the `regression_coreset`
   (Phase 6 input) and serve as a **positive reference** in the
   patcher prompt,
2. it CANNOT create a promotable claim by itself,
3. it CANNOT update `latest_executor_action` (the rule prose) — only
   mixed-group evidence rewrites the rule,
4. an all_success entry on an existing pattern just appends a row to
   `remedy_log` with `patch: regression-anchor-only`.

This is the framework's core defense against capability/skill-gap
conflation. Encoded once here in the schema; the patcher's quantitative
routing (Phase 4) cross-checks the same constraint.

---

## 3. Prompt structure (delta over SkillGrad's MOMENTUM_PROMPT)

### Sections that stay verbatim

- §1 The skill, the executor, and your role
- §2 Pattern record schema (just add the two new fields)
- §3 Per-task overlay schema (add the three new slots)
- §4 Anchor convention
- §5 WORKFLOW-THEMES rules
- §6 Bootstrap clarification (iter 1)
- §7 Information-loss safeguards
- §8 MUST NOT
- §9 Worked example (replace with a group-aware example)

### New additions

**§2a — Group-type semantics (new sub-section under §2)**

Insert after the schema block:

```
For each group, you receive its `group_type` (mixed | all_fail |
all_success) and reward distribution. Use these to update the
pattern's `evidence_profile`:

- mixed group with clean advantage split (max - min advantage ≥ 0.5
  on a centered 0..1 reward) → mixed_support += 1, append
  (iter, task_id) to source_groups.
- mixed group with weak split → mixed_support += 1 (still counts);
  the weak/strong distinction may matter at routing time but not in
  the profile.
- all_success group corroborating an existing pattern →
  all_success_support += 1.
- all_fail group whose aggregated signal maps to a pattern →
  all_fail_support += 1.
- evidence directly contradicting the pattern's stated rule →
  contradiction_count += 1.

`current_strength` is then derived per the rule in §2.2.
`peak_strength = max(peak_strength, current_strength)`.

**Hard constraints (encode in code, not just prompt):**
- a pattern whose evidence_profile has mixed_support + all_success_support == 0
  cannot be promoted to L2 (current_strength is `low`).
- an all_success entry can append to remedy_log with
  `patch: regression-anchor-only` and feed the regression coreset,
  but cannot rewrite `latest_executor_action`.
```

**§3a — Overlay rules for the three group types (new sub-section under §3)**

```
Per overlay entry, the `group_type` slot determines how `pattern` and
`proposed_change` are filled:

- mixed:
    Identify decision points where high-advantage rollouts diverge
    from low-advantage rollouts. The `gap` should describe the
    behavior the low-advantage rollouts shared. The `proposed_change`
    encodes the rule that the high-advantage rollouts followed.
    This is the only group type that can rewrite a pattern's
    `latest_executor_action`.

- all_success:
    Do NOT produce a `proposed_change`. Set `pattern: no-actionable-
    signal` UNLESS this group's success contradicts the patcher's
    earlier prediction (i.e., the skill says "this should fail" or
    "approach X is needed" but the rollouts succeeded with approach
    Y). In that case, narrow the existing claim's trigger condition
    only — do NOT introduce new prose into latest_executor_action.

- all_fail:
    Aggregate the K failed trajectories' shared signal into a single
    proposed_change candidate. Increment all_fail_support on the
    pattern; the pattern's current_strength stays at `low` until a
    mixed group corroborates. The patcher will only place this
    content in pending / L3 case-memory.
```

**§9 worked example replacement**

Show three overlay entries in one iteration:
- one mixed group → high-confidence pattern update
- one all_fail group → low-strength candidate
- one all_success group → either skipped or refines existing claim

(Detailed example deferred until Phase 3 implementation; structure
mirrors SkillGrad's existing §9 with the extra slots filled.)

---

## 4. Inputs / outputs (unchanged structure)

### Inputs

- `batch_diagnoses.md` — assembled per-task diagnoses, one block per
  *group*. Each block now contains:
  - the bench's `instruction` text
  - the group's reward distribution + advantages
  - K per-rollout assessments (for mixed: highlight high vs low
    advantage; for all_fail: union of common failure features; for
    all_success: shared success features)
  - the existing free-form diagnosis prose (still produced by Phase 2's
    group_diagnoser, just with group context attached)

### Outputs

- `momentum_memory.md` — pattern record (with `evidence_strength`)
- `momentum_overlay.md` — N per-task blocks (each with `group_type` +
  `group_advantage_summary`) + `## WORKFLOW-THEMES`

The patcher (Phase 4) reads both. The regression coreset (Phase 6)
gets fed all-success groups separately (not via momentum).

---

## 5. Where the implementation will live

```
prompts/group_momentum.py   # extends MOMENTUM_PROMPT with the new sections
pipeline/group_momentum.py  # async wrapper; same shape as pipeline/momentum.py
                            # but accepts group_results instead of bare assessments
```

`pipeline/momentum.py` (SkillGrad-original) stays untouched as the
single-trajectory baseline for ablation.

The training loop (`pipeline/training.py`) Phase 3 wiring becomes:

```python
if iter_num >= 2:
    await run_group_momentum(           # ← new
        group_results,                   # list of N group_result dicts from Phase 2
        previous_record_path=...,
        skills_dir=...,
        record_output_path=...,
        overlay_output_path=...,
        skill_name=bench.skill_name,
    )
```

---

## 6. Downgrade mechanism (designed in Phase 3, ENFORCED in Phase 6)

For long-horizon stability (≥100 batch experiments). DESIGN now so the
schema captures the right state; ENFORCE later when we have data.
Phase 1-3 implementations only need to RECORD the data; demotion
triggers fire in Phase 6 once the regression-coreset infrastructure
exists.

### State machine

Every pattern's `current_strength` and downstream artifacts (pending
pool entries, auxiliary memory chapters) can be DOWNGRADED based on
explicit triggers — never silently. Three downgrade paths:

1. **`pending → stale_pending`**
   - trigger: `current_iter - last_mixed_iter ≥ W_pending` (default
     W_pending = 10 batches; tunable). The pattern was promising but
     no mixed-group evidence has reaffirmed it.
   - effect: pattern stops appearing in patcher inputs; remains in
     pattern record for audit; can be revived if a mixed group later
     fires.

2. **`core → flagged_for_review`** (does NOT auto-rollback)
   - trigger A: `contradiction_count` accrued in the last W_core
     batches ≥ 1 (default W_core = 5).
   - trigger B: regression coreset shows `delta < 0` for this pattern
     in the last W_core batches.
   - effect: patcher receives the pattern with a `flagged: true`
     annotation; expected response is to refine trigger or split the
     pattern, not auto-rollback. Hard rollback is a separate manual
     decision (deferred to Phase 6+ tooling).

3. **`auxiliary → archived`**
   - trigger A: `retrieval_count = 0` over the last W_aux batches
     (default W_aux = 20).
   - trigger B: `retrieval_helpfulness < threshold` (requires
     instrumentation — see "open instrumentation" below).
   - effect: chapter moves to `archived/` directory; not loaded; can
     be revived manually.

### Default windows (subject to ablation)

```
W_pending = 10 batches
W_core    = 5  batches
W_aux     = 20 batches
```

These are starter values; expect to tune in long-horizon experiments.

### Open instrumentation (does not block Phase 3)

`retrieval_helpfulness` (auxiliary archive trigger B) needs the
executor to emit a `helpful=True/False` signal after consulting an
auxiliary memory chapter. This is a new instrumentation point added
in Phase 4 (when retrieval routing lands). For now: only trigger A
(retrieval_count = 0) is implementable.

### Phase 1-3 obligation: record only

Phase 3 implementation must populate:
- `last_mixed_iter` on every pattern update,
- `contradiction_count` accumulation,
- `source_groups` audit trail,

so Phase 6 has the data to fire the demotion triggers. **Phase 3 must
NOT actually demote anything yet** — the triggers are dormant.

---

## 7. Open design points (decide at implementation time)

1. **Advantage threshold for "clean split"**: start at 0.5 of soft-
   accuracy range; v1 uses a binary clean / weak split (per the
   group_advantage helper in `pipeline/group_execution.py`). May need
   per-bench tuning (WTQ binary 0/1 scores → effective range smaller).
   Ablate post-pilot.
2. **WORKFLOW-THEMES gating** (TBD — verify SkillGrad's prompt §5
   first): SkillGrad's `MOMENTUM_PROMPT` §5 fires WORKFLOW-THEMES from
   "successful entries" — under K=1 those are cross-version contrastive
   successes. Under K>1, a "successful entry" needs a precise mapping:
   - Option A: `signal: success` (binary `is_correct` of the
     representative rollout) — simplest, matches SkillGrad's
     existing semantics literally.
   - Option B: only mixed-group entries' high-advantage rollouts
     count as "successful" — semantically richer but more invasive.
   - Option C: weighted by group_advantage_summary's high_adv
     fraction — finest grained, hardest to get right in v1.
   ACTION: read `prompts/momentum.py` §5 + `prompts/momentum.py`
   §1-4 for the exact "successful entry" definition before choosing.
   Estimated 5 minutes; do not pick this design without doing the
   read.
3. **Whether to expose `peak_strength` to the patcher**: routing only
   reads `current_strength`. `peak_strength` is audit-only by default.
   Argument for exposing peak: lets the patcher reason about
   "previously-trusted-but-now-flagged" patterns. Argument against:
   bloats prompt + risks the patcher second-guessing the routing rule.
   Default: NO, peak stays internal.

---

## 8. Out of scope for Phase 3

Explicitly NOT in this phase:
- Quantitative routing thresholds (Phase 4).
- The patcher's response to current_strength / evidence_profile
  (Phase 4).
- Regression coreset construction from all_success groups (Phase 6).
- Demotion trigger firing — schema records, Phase 6 enforces (§6).
- `retrieval_helpfulness` instrumentation (Phase 4 when retrieval
  routing exists).
- Embedding-based pattern clustering (Phase 4+ ablation; pattern
  matching stays LLM-driven for v1).
- Freshness windows tuned to specific iteration counts — defaults
  in §6 are placeholders, real values come from long-horizon data.

---

## 9. Framing — what role this section plays in the paper

**evidence_profile is supporting infrastructure, not the headline
contribution.** The paper's lead is:

> *We route the within-task K-rollout group-relative advantage into
> the skill artifact, where SkillRL routes it into LLM weights and
> SkillGrad has no group structure at all.*

Phase 3 lets that pitch land cleanly: the schema additions here
record the per-group evidence shape so Phase 4 routing can act on
**which evidence form** corroborated the pattern. Without this, the
patcher would have to re-derive evidence form from raw diagnoses
prose every iteration, and the all_fail-cannot-promote constraint
would be a soft prompt rule rather than a code-enforceable invariant.

A reviewer reading the contribution list should NOT come away
thinking "they added structure to momentum." SkillGrad's momentum
already has structure. What we added is the link between *group
evidence shape* and *pattern routing decisions* — and that link only
matters because Phase 1's K-rollout group structure exists.

---

## 10. Acceptance criteria

When Phase 3 is implemented, the smoke test is:

1. Run a 2-iter G2B training pass with K=4 on 4 tasks per batch.
2. Inspect `iter_2/momentum_overlay.md`:
   - 4 overlay blocks, each with `group_type` slot filled.
   - `## WORKFLOW-THEMES` block present.
3. Inspect `iter_2/momentum_memory.md`:
   - At least one pattern with `evidence_strength` field.
   - `group_support` block populated.
4. No pattern marked `evidence_strength: low` is referenced as a
   `core_promote` candidate in the patcher's downstream output (Phase 4
   not yet wired, so just spot-check the LLM's free-form output for
   non-violation).

If all four hold, Phase 3 ships.
