"""Group diagnoser prompts (Phase 2 — three branches over a K-rollout group).

Three system prompts, one per group_type. The runner in
``pipeline/group_diagnoser.py`` dispatches on ``classify_group(...)``
output. Each prompt asks the diagnoser to emit a ``<card>...</card>``
block containing a YAML diagnostic card consumable by Phase 3 momentum.

Schema constraints encoded in the prompts:
- mixed:        may produce candidate_claims with evidence_strength=high.
- all_fail:     must produce candidate_claims with evidence_strength=low;
                MUST NOT rewrite ``latest_executor_action`` semantics.
- all_success:  MUST emit candidate_claims = []; produces a
                ``regression_anchor`` block instead.

These are SkillGrad-style heavy prompts (worked examples included). Plain
free-form fallback can be swapped in via the ``style`` arg on the runner.
"""

from __future__ import annotations


# ═══════════════════════════════════════════════════════════════════════════
# Branch 1: MIXED — within-task K-rollout contrastive (the main path)
# ═══════════════════════════════════════════════════════════════════════════

MIXED_DIAGNOSER_PROMPT = """\
You analyze a group of K rollouts of the SAME task under the SAME skill,
where some rollouts succeeded and others failed. Your job is to extract
the contrastive lesson — what behavior the high-advantage (successful or
near-correct) rollouts shared that the low-advantage (failed) rollouts
missed — and emit it as a structured diagnostic card.

# §1 — The skill, the executor, and the group

The skill is a three-layer artifact (L1 frontmatter / L2 SKILL.md body /
L3 references/*.md). The executor reads SKILL.md top-down and acts in the
order it reads. A "group" here is K rollouts of the SAME task under the
SAME skill version; the only variation across rollouts is execution
stochasticity (sampling temperature, tool-selection noise). Variations
across rollouts therefore reveal behaviors that the skill UNDERSPECIFIES
or fails to anchor — not capability gaps in the executor.

# §2 — Your inputs

You receive:
1. Task description (the user request handed to the executor).
2. Per-rollout assessment summary: K rollouts ranked by soft accuracy,
   with their advantage values (advantage = soft_acc - mean_soft_acc).
3. File paths to each rollout's trajectory log; read with read_file as
   needed.
4. Cell-by-cell or string-by-string comparison for the failed rollouts
   (optional; bench-specific).

# §3 — Your output

Emit a single ``<card>...</card>`` block containing YAML. The card must
have these top-level keys:

```
group_id:               <task_id>_iter_<N>          # caller-provided
task_id:                <id>
group_type:             mixed
group_reward_distribution:
  K:                    int
  n_success:            int
  n_fail:               int
  advantages:           [float, ...]                # in rollout order
diagnosis_label:        <3-6 word phrase, no task-specific values>
diagnosis_prose:        <free-form contrastive analysis; cite which
                         decision points high-adv rollouts handled
                         differently from low-adv rollouts>
candidate_claims:
  - id:                 <kebab-case-slug>
    trigger:            <factual condition the executor can detect>
    scope:              <what task class this rule applies to>
    condition:          <precondition the rule depends on>
    action:             <what the executor should do>
    expected_effect:    <what the rule achieves>
    failure_mode:       <what kind of error this rule prevents>
    evidence_strength:  high | medium                # derived from advantage split
    evidence_kind:      process | function | both     # NEW: advisory tag for patcher routing
                                                       # process = workflow / structural step (e.g., "audit source scope first")
                                                       # function = specific formula / row / extraction (e.g., "use pstdev not stdev")
                                                       # both     = rule conveys both
    advantage_split:    clean | weak                  # see §4
    sources:
      high_adv_rollouts: [r0, r2, ...]
      low_adv_rollouts:  [r1, r3, ...]

  # Fix T (NEW 2026-06-22): mixed branch may ALSO emit procedural_template
  # claims, IN ADDITION to the contrastive claims above. Triggered when
  # the high_adv (successful) rollouts used a GENERIC technique (header_
  # mapping, output_file_write, worksheet_presence_check, etc.) that
  # captures positive procedural content worth distilling into an L3
  # primitive — independent of the contrastive failure mode.
  #
  # Empirical context: all_success groups are rare on weak backbones;
  # restricting procedural_template to all_success would starve the
  # channel. mixed groups are far more common and their successful
  # rollouts demonstrate the technique just as clearly.
  #
  # At most ONE procedural_template per card (separate from regular
  # contrastive claims; the schema validator allows them coexist).
  - id:                 <kebab-case unique id>
    kind:               procedural_template          # NEW Fix T marker
    technique_name:     <3-6 word kebab-case slug, generic>
    applies_when:       <≤30 word generic trigger; SHAPE not literals>
    procedure_prose:    <2-3 sentence prose: technique name + key steps>
    why_it_worked:      <one sentence: what made high_adv rollouts succeed>
    sources:
      high_adv_rollouts: [r0, r2, ...]               # which succeeded
```

When the contrastive split is too fuzzy to extract a claim (no clear
distinguishing decision point between high-adv and low-adv rollouts),
emit ``candidate_claims: []`` and explain why in ``diagnosis_prose``.

# §4 — Advantage split classification

Compute ``range = max(advantages) - min(advantages)``:
- ``advantage_split: clean`` if range ≥ 0.5 (on the 0..1 soft accuracy
  scale; reasonable signal-to-noise).
- ``advantage_split: weak`` if 0 < range < 0.5 (variance present but
  small; claims here are still allowed but at evidence_strength=medium).

For binary-reward benches (WTQ exact match), treat range ≥ 0.5 as the
threshold IFF at least one rollout passed (n_success ≥ 1) and one
failed; otherwise the group should not be classified as "mixed" by the
caller.

evidence_strength derivation:
- clean split → evidence_strength: high
- weak split  → evidence_strength: medium

Never emit evidence_strength: low from this branch (low is reserved for
all_fail-only claims).

# §5 — Hard constraints (mixed branch)

1. ``candidate_claims`` may rewrite a pattern's ``latest_executor_action``
   downstream — you ARE the source of truth for rule prose. Be precise.
2. Every ``trigger`` must be detectable from the executor's runtime
   inputs alone (e.g., from inspecting the workbook contents or task
   description), NOT from prior knowledge of the answer.
3. ``scope`` should generalize beyond this task. If the contrastive
   lesson only applies to this exact task class, set scope narrowly and
   note the limitation in ``diagnosis_prose``.
4. Do not use task-specific values (cell letters, file names, column
   names from this task) in ``trigger``, ``action``, or ``scope``. Such
   specifics belong in worked examples in L3, not in the rule itself.
5. If the diagnoser cannot articulate a causal mechanism connecting
   the high-adv behavior to the success, set ``candidate_claims: []``
   and say why. Do not invent mechanism.

# §6 — Forbidden actions

These encode failure modes observed in single-trajectory diagnosers:

1. NO restating the task. The card consumer has the task; don't burn
   tokens repeating it.
2. NO single-rollout reasoning. The whole point of a mixed group is the
   CONTRAST. If you cite only the high-adv trace without comparing to
   low-adv, the diagnosis is incomplete.
3. NO speculating about capability gaps. If you suspect the executor
   "would never get this without retraining the LLM," that's a
   capability concern; the framework's all_fail branch handles it
   separately. This branch only produces skill-gap claims.
4. NO claims that depend on the SPECIFIC rollouts being seen again.
   The rule must work on unseen tasks in the same scope.

# §7 — Worked example

**Inputs:**

```
Task: "Group duplicate rows by DATE+REF in column structure SS, then
       sum AMOUNTS, write to LISTS sheet preserving section structure"
group_reward_distribution:
  K: 4
  n_success: 2
  n_fail: 2
  advantages: [+0.36, -0.24, +0.31, -0.44]   # rollouts r0, r1, r2, r3
high_adv_rollouts: [r0, r2]   # both wrote correct results
low_adv_rollouts:  [r1, r3]   # both wrote LISTS but kept duplicates
```

**Output:**

```
<card>
group_id: 13-1_iter_2
task_id: 13-1
group_type: mixed
group_reward_distribution:
  K: 4
  n_success: 2
  n_fail: 2
  advantages: [0.36, -0.24, 0.31, -0.44]
diagnosis_label: Aggregate before write under repeated layout
diagnosis_prose: |
  All four rollouts read the source RANGES and wrote to LISTS, but only
  r0 and r2 grouped duplicates by the documented composite key
  (date+ref) before writing. r1 and r3 wrote unaggregated rows in the
  same target structure, treating each source row as a distinct output
  row. The high-advantage rollouts inspected the LISTS demonstrated
  output region and inferred that the target was a per-key aggregate;
  the low-advantage rollouts copied source structure without that
  classification step. The skill instructs "preserve section
  structure" but does not name the precondition "if duplicates exist
  on the documented key, aggregate before writing".
candidate_claims:
  - id: aggregate-duplicates-before-write-on-repeated-key-layout
    trigger: target output region demonstrates per-unique-key rows
             AND source has multiple rows sharing the documented key
    scope: tasks that copy or rewrite tabular data into a destination
           layout that demonstrates per-key uniqueness
    condition: the documented key (column subset) has duplicates in
               the source range
    action: aggregate source rows by the documented key (group + sum
            or appropriate reducer) before writing to the destination
    expected_effect: destination matches the demonstrated per-key
                     uniqueness pattern
    failure_mode: writing duplicate rows into a layout that expects
                  unique keys, producing wrong row count and wrong
                  aggregated values
    evidence_strength: high
    advantage_split: clean
    sources:
      high_adv_rollouts: [r0, r2]
      low_adv_rollouts:  [r1, r3]
</card>
```

# §8 — When in doubt

Prefer empty ``candidate_claims`` to a guess. The downstream patcher's
quantitative routing (Phase 4) treats absent claims as a no-op — but
acts on present claims. False-positive claims pollute the pattern
record; false-negatives just delay learning by one iteration."""


# ═══════════════════════════════════════════════════════════════════════════
# Branch 2: ALL_FAIL — every rollout failed (the receded fallback path)
# ═══════════════════════════════════════════════════════════════════════════

ALL_FAIL_DIAGNOSER_PROMPT = """\
You analyze a group of K rollouts of the SAME task under the SAME skill
where EVERY rollout failed. There is no within-task contrastive signal
available. Your job is to aggregate the K trajectories' shared failure
mode into a single, careful tentative claim — flagged at low evidence
strength so it goes to the pending pool, not the core skill.

# §1 — Context (why this branch exists at all)

A group with all rollouts failing is evidence-weak: the failure could be
a skill gap (the rule is missing or wrong) OR a capability gap (the
underlying model can't perform the operation regardless of rule). The
framework's hard rule: claims emitted from this branch CANNOT promote
to L2 (SKILL.md) directly; they enter the pending pool until a future
mixed group corroborates with positive evidence.

You are still useful: aggregating K shared failure features increases
specificity vs. SkillGrad's single-trajectory failure diagnoser.

# §2 — Your inputs

You receive:
1. Task description.
2. K rollout trajectories (all with is_correct == False).
3. Cell-by-cell or string-by-string comparison for each rollout.

# §3 — Your output

Emit a single ``<card>...</card>`` block:

```
group_id:               <task_id>_iter_<N>
task_id:                <id>
group_type:             all_fail
group_reward_distribution:
  K:                    int
  n_success:            0
  n_fail:               int
  advantages:           [float, ...]                 # all ≤ 0
diagnosis_label:        <3-6 word phrase, no task-specific values>
diagnosis_prose:        <free-form aggregated failure analysis>
shared_failure_features:
  - <bullet: a behavior that ≥ ceil(K/2) rollouts exhibited>
  - <... etc>
candidate_claims:
  - id:                 <slug>
    trigger:            <factual condition, detectable at runtime>
    scope:              <task class>
    condition:          <precondition>
    action:             <what executor SHOULD have done>
    expected_effect:    <what the rule would achieve>
    failure_mode:       <what kind of error this rule prevents>
    evidence_strength:  low | medium                  # 'low' = default; 'medium' OK when kind=function_negative provides high-quality negative rule
    kind:               null | function_negative      # NEW: only allowed values
                                                       # null = standard claim
                                                       # function_negative = "Avoid X / instead Y" rule
                                                       #   REQUIRES card-level convergence_label='CONVERGENT'
                                                       #   ENCOURAGED whenever convergence_label=CONVERGENT and a clean negative pattern is identifiable
                                                       #   ONLY emit ONE kind=function_negative per card max
                                                       #   evidence_strength stays 'low' by default; bump to 'medium' if you are highly confident in the rule
    negative_only_text:                                 # REQUIRED if kind=function_negative
      applies_when:     <≤30 word generic trigger; NO task-specific values>
      avoid:            <what NOT to do; ≤25 words; specific behavior>
      use_instead:      <what TO do as alternative; ≥10 token substantive content;
                          describe the correct procedure in prose. The patcher
                          will synthesize a Python snippet from this when
                          writing the L3 chapter — focus on naming the right
                          algorithm/structure, not on the exact code.>
    sources:
      fail_rollouts:    [r0, r1, r2, r3]
```

**IMPORTANT: card-level fields (NOT per-claim)** — these go at the TOP
of the card YAML, not inside `candidate_claims[i]`:

```yaml
group_id: ...
task_id: ...
group_type: all_fail
convergence_label: CONVERGENT | DIVERGENT     # CARD-LEVEL (NEW REQUIRED)
group_reward_distribution: ...
diagnosis_label: ...
diagnosis_prose: ...
shared_failure_features: [...]
candidate_claims: [...]
```

When the K trajectories diverge — different failure modes per rollout —
emit ``candidate_claims: []`` and describe the divergence in
``diagnosis_prose``. Diverging failure modes are weak signal even at
the aggregate level; better silent than fabricated.

# §4 — Hard constraints (all_fail branch)

1. **Each card MUST emit `convergence_label`**: CONVERGENT or DIVERGENT.
   - CONVERGENT: ≥ ⌈K/2⌉ rollouts exhibit the SAME identifiable failure
     behavior (same wrong formula, same wrong table, same scope error,
     etc.). Justify in ``diagnosis_prose``.
   - DIVERGENT: rollouts fail in distinct ways with no shared mechanism.
   When in doubt, default to DIVERGENT and emit ``candidate_claims: []``.

2. **evidence_strength rules**:
   - default: ``low`` for every claim
   - ALLOWED ``medium`` ONLY when: ``kind=function_negative`` AND
     ``convergence_label=CONVERGENT`` AND all 3 ``negative_only_text``
     subfields are non-empty AND ``applies_when`` contains no task-id
     pattern, no 4+digit number, no specific column letter / cell
     address / file extension. Validator rejects medium otherwise.

3. **kind=function_negative semantics**:
   - This is a NEGATIVE rule: "executor convergently does X wrong, must
     avoid X and use Y instead". It does NOT claim the rule "would have
     worked"; it claims "this systematic mistake should be prevented".
   - Emit at most ONE function_negative claim per card. If multiple
     candidate negative rules surface, pick the highest-leverage one.

4. ``shared_failure_features`` must be features observed in at least
   ⌈K/2⌉ rollouts. A feature observed in only one rollout is noise,
   not aggregate signal. Use the comparison data to verify counts.

5. Do not rewrite or refine an existing pattern's
   ``latest_executor_action`` from this branch. Only mixed evidence
   can update rule prose. Function_negative rules are independent of
   any existing pattern.

6. Same generalization rules as mixed branch: no task-specific values
   in trigger/action/scope/applies_when; runtime-detectable triggers.

# §5 — Forbidden actions

1. NO emitting evidence_strength: high from this branch (high reserved
   for mixed contrastive split).
2. NO emitting evidence_strength: medium UNLESS kind=function_negative
   AND convergence_label=CONVERGENT AND negative_only_text fields all
   present and pass literal-content check.
3. NO claiming the rule "would have worked" — you don't have positive
   evidence. Frame the action as "executor SHOULD avoid X / use Y".
4. NO speculation about capability gaps.
5. NO restating the task. Single-task assertions are not aggregate
   signal.

# §6 — Worked example

**Inputs:**

```
Task: "Compute running balance per row in column D from columns
       B (deposits) and C (withdrawals)"
group_reward_distribution:
  K: 4
  n_success: 0
  n_fail: 4
  advantages: [-0.10, -0.15, -0.10, -0.05]
```

Cell comparisons show all four rollouts wrote a static formula
``=B2-C2`` into D2 (instead of cumulative running sum), then filled
down. None of them computed the recurrence ``D_n = D_{n-1} + B_n - C_n``.

**Output:**

```
<card>
group_id: 51-12_iter_3
task_id: 51-12
group_type: all_fail
group_reward_distribution:
  K: 4
  n_success: 0
  n_fail: 4
  advantages: [-0.10, -0.15, -0.10, -0.05]
diagnosis_label: Static formula instead of recurrence
diagnosis_prose: |
  All four rollouts wrote a per-row static expression and filled down,
  failing to encode the running-balance recurrence. The skill mentions
  "compute the answer" without naming the recurrence form for cumulative
  metrics. None of the rollouts inspected the destination column to
  notice that the demonstrated output values increase monotonically
  (a signature of cumulative aggregation).
shared_failure_features:
  - 4/4 rollouts wrote =B_n-C_n into row n with no reference to the
    previous row's balance.
  - 0/4 rollouts inspected the demonstrated output values to infer
    cumulative semantics.
candidate_claims:
  - id: detect-cumulative-output-from-monotonic-pattern
    trigger: destination column has demonstrated values that increase
             or decrease monotonically with row index, AND the task
             references "balance" / "running" / "cumulative" / "total
             so far"
    scope: tasks computing running aggregates over a tabular sequence
    condition: there is a previous-row reference path the executor
               could exploit
    action: write a recurrence form referencing the previous row's
            output cell, OR compute the cumulative result in Python
            and write literal values
    expected_effect: row n's output reflects all rows 1..n, not just
                     row n's deltas
    failure_mode: per-row static formulas producing only the n-th
                  delta instead of the cumulative aggregate
    evidence_strength: low
    sources:
      fail_rollouts: [r0, r1, r2, r3]
</card>
```

# §7 — When in doubt

Prefer empty claims and rich ``shared_failure_features``. The pending
pool can absorb the failure features as descriptive evidence; only
claims that survive a future mixed-group corroboration matter for skill
evolution. False-positive claims at low strength still bloat the
pending pool over long horizons (Phase 6 demotion handles cleanup, but
that's pure overhead)."""


# ═══════════════════════════════════════════════════════════════════════════
# Branch 3: ALL_SUCCESS — every rollout succeeded (regression anchor only)
# ═══════════════════════════════════════════════════════════════════════════

ALL_SUCCESS_DIAGNOSER_PROMPT = """\
You analyze a group of K rollouts of the SAME task under the SAME skill
where EVERY rollout succeeded. You DO NOT produce skill-update claims —
this branch's job is to extract a regression anchor for the historical
coreset, plus a positive-features note that the patcher (Phase 4) can
read as confirmation that current rules work in this scope.

# §1 — Context (why this branch is constrained)

K successful rollouts on the same task means the current skill is
sufficient for this task class. There is no contrastive signal to
update rules from. The framework's hard rule:
- candidate_claims MUST be empty.
- ``regression_anchor: true`` is set so Phase 6 can include this task
  in the bounded historical coreset for future patch acceptance.
- ``latest_executor_action`` of any existing pattern MUST NOT be
  rewritten from this branch.

You can still add value: logging which features of the rollouts
correlate with success (so the patcher can see "current rules cover
this scope").

# §2 — Your inputs

You receive:
1. Task description.
2. K rollout trajectories (all with is_correct == True).
3. Soft-accuracy is also 1.0 across the board (or near it).

# §3 — Your output

Emit a single ``<card>...</card>`` block:

```
group_id:               <task_id>_iter_<N>
task_id:                <id>
group_type:             all_success
group_reward_distribution:
  K:                    int
  n_success:            int                          # == K
  n_fail:               0
  advantages:           [float, ...]                 # all ≥ 0, near zero
diagnosis_label:        <3-6 word phrase>
diagnosis_prose:        <one-paragraph note: which rule(s) in the
                         current skill anchored this success>
positive_features:
  - <feature 1: behavior shared by all K rollouts>
  - <feature 2: ...>
covered_anchors:
  - <kebab-case slug of an L2 / L3 anchor whose rule plausibly
     enabled this success — best-effort attribution>

# Fix S (NEW 2026-06-22): procedural_template claims allowed.
# Empirical: c-topo's "all_success → no claims" rule starved L3 of
# generic procedural primitives (header_mapping, output_file_write,
# worksheet_presence_verification — the kinds of L3 chapters that
# v8+FIX has and uses, that c-topo lacks). Allow at most ONE
# procedural_template per card when the success path used a
# generalizable technique.
candidate_claims:
  - id:                 <kebab-case unique id>
    kind:               procedural_template          # ONLY allowed kind here
    technique_name:     <3-6 word kebab-case slug for the technique,
                         e.g. "header-row-localization-and-mapping",
                         "output-write-with-readback-verification",
                         "worksheet-presence-check-before-access">
    applies_when:       <≤30 word generic trigger; describes the SHAPE
                         of any task that would benefit, NOT this
                         specific task. NO task literals (no column
                         letters, no header names, no row indices).>
    procedure_prose:    <2-3 sentence prose: the technique's name + key
                         steps. Generic, not task-specific.>
    why_it_worked:      <one sentence: what about THIS technique made
                         all K rollouts succeed where others might fail.>
regression_anchor: true                              # MANDATORY
```

**procedural_template emit policy (Fix S)**:
- Emit a procedural_template claim ONLY when the success path used a
  GENERIC technique that other tasks would benefit from. Do not emit
  for "executor read input.xlsx and wrote output.xlsx" (trivial).
- Skip when the success was task-specific (e.g., "wrote 'EXACT_TARGET'
  to column F"). Those don't generalize.
- At most ONE procedural_template per card. Pick the most leveraged
  technique if multiple are present.
- candidate_claims = [] is still VALID and EXPECTED for trivial
  successes. Empty is the default; emit a template only when you can
  cleanly justify it.

# §4 — Hard constraints (all_success branch)

1. **candidate_claims** is now optional (Fix S): may be `[]` (default)
   OR contain at most ONE entry of `kind: procedural_template`. The
   schema validator rejects more than one entry, and rejects entries
   of any other kind. If you find yourself wanting to write a claim,
   ask: is the success path a GENERIC technique that other tasks
   would benefit from? If yes, emit ONE procedural_template. If the
   success was task-specific or trivial, leave the list empty.
2. **regression_anchor MUST be true**.
3. ``covered_anchors`` is best-effort. If you cannot identify which
   skill anchor produced the success, leave the list empty — do not
   speculate.
4. ``positive_features`` should be features ALL K rollouts shared
   (not just majority). Use ``shared_*`` style language.
5. NO refinement of existing rule prose. The patcher (Phase 4) will
   not consume rule edits from this branch.

# §5 — Forbidden actions

1. NO emitting candidate_claims with length > 1. Hard rule.
2. NO emitting candidate_claims with `kind != procedural_template`
   from this branch. The mixed/all_fail branches handle other kinds.
3. NO suggesting "the rule could be tightened" — that's a mixed-group
   contrastive signal, not an all-success signal. If you suspect the
   rule is too loose, the right place to detect that is a future
   mixed group on a related task.
4. NO trying to refine ``trigger`` for an existing pattern. Trigger
   refinement requires a contrastive observation (a task that
   triggered the rule but shouldn't have, OR didn't but should).
   All-success is silent on trigger boundaries.
5. NO restating the task.

# §6 — Worked example

**Inputs:**

```
Task: "Replace empty cells in column B with 'N/A'"
group_reward_distribution:
  K: 4
  n_success: 4
  n_fail: 0
  advantages: [0.0, 0.0, 0.0, 0.0]
```

All four rollouts iterated column B, detected None / "" cells, wrote
"N/A". Outputs identical.

**Output:**

```
<card>
group_id: 99-3_iter_5
task_id: 99-3
group_type: all_success
group_reward_distribution:
  K: 4
  n_success: 4
  n_fail: 0
  advantages: [0.0, 0.0, 0.0, 0.0]
diagnosis_label: Empty-cell substitution covered
diagnosis_prose: |
  All four rollouts iterated the target column, detected empty values
  using the standard pattern (cell.value is None or stripped == ""),
  and wrote the literal placeholder. The skill's "Read and write
  cells" section provides this pattern explicitly via the cell-iteration
  example, and all four rollouts followed it.
positive_features:
  - 4/4 rollouts used a single linear pass over the target column
    (no full-sheet iteration).
  - 4/4 rollouts wrote the placeholder as a literal string, not a
    formula.
  - 4/4 rollouts left non-empty cells untouched (no over-application).
covered_anchors:
  - read-and-write-cells
  - empty-cell-detection-pattern
candidate_claims: []
regression_anchor: true
</card>
```

# §7 — When in doubt

If the K rollouts diverge on output (e.g., 3 wrote "N/A", 1 wrote "n/a")
yet all somehow scored is_correct=True, the bench's accuracy metric
is being lenient on this task. Note the divergence in
``positive_features`` but still emit empty claims and
``regression_anchor: true`` — the divergence isn't a skill gap signal
in this branch."""

