"""v8 group-aware diagnoser prompts.

- CONTRASTIVE_DIAGNOSER_PROMPT: reuse SkillGrad's existing prompt verbatim
  (already neutral about "same skill version vs different"); v8 just reorders
  args (FAIL first, PASS second) for within-group contrastive on mixed groups.

- ALL_FAIL_CLUSTERING_PROMPT: NEW. Takes K failed traces of the same task
  under the same skill, classifies convergent vs divergent, and produces a
  single diagnosis tailored to which case applies.
"""

# Direct re-export so v8 can swap diagnoser_prompts.WITHIN_GROUP_CONTRASTIVE_PROMPT
# without touching the existing prompts/diagnoser.py file.
from prompts.diagnoser import CONTRASTIVE_DIAGNOSER_PROMPT as WITHIN_GROUP_CONTRASTIVE_PROMPT


MIXED_GROUP_K_TRACE_PROMPT = """\
You analyze K executions of the SAME task under the SAME skill artifact, where \
some rollouts succeeded and some failed. The K rollouts differ only in random \
sampling (no skill version difference). Your job is to find what behavioral \
choice separates the success rollouts from the failure rollouts — this is the \
deciding factor the skill should learn.

You receive: the task description, a cell-by-cell comparison from one failed \
rollout (other failures are similar), and file paths to all K execution traces \
labeled with their PASS/FAIL outcome.

Workflow:

1. Read every trace. Note for each rollout: which approach it took (library, \
formula vs literal, code structure), which assumptions it made, which \
verification steps it performed.

2. Identify the SUCCESS-group's common behavior — what did the passing \
rollouts all do (or check, or avoid) that produced the correct output? \
Identify the FAILURE-group's common behavior — what did the failing rollouts \
all do that produced the wrong output?

3. Determine the SINGLE deciding factor — the one choice point where the two \
groups diverged. This is what the skill should learn.

4. Assess robustness: does the success approach generalize to similar tasks, \
or did the passing rollouts get lucky on this particular input?

5. **Match abstraction level to deciding factor**: if the deciding factor is a \
*workflow* choice (inspect first / output modality / verify exact write), the \
diagnosis should be process-level. If the deciding factor is a *formula or \
function syntax* choice (which Excel function to use, how to combine ranges, \
how to wrap an array criteria, etc.), the diagnosis MUST include the specific \
formula syntax the success-group used (verbatim if possible) AND a Python \
equivalent if a literal computation would also work. The skill should learn \
function-level knowledge with concrete syntax — not abstract workflow advice — \
when the deciding factor is at the formula/function level.

Write your analysis inside a <diagnosis> block. Start with a LABEL — a short \
phrase (3-6 words) naming the deciding factor in general terms (not \
task-specific). Then write your analysis in plain prose:

- Briefly describe the SUCCESS-group's behavior and the FAILURE-group's \
behavior (1-2 sentences each).
- State the deciding factor explicitly.
- Assess robustness.
- State what specific knowledge the skill should learn so this task \
class becomes deterministic, not sampling-dependent.
- If the deciding factor is formula-level: include the specific Excel formula \
construction the success-group used, and a Python equivalent.

# Example (process-level deciding factor)

Task: "Fill column B with the running total of column A values."
Cell comparison from failed rollout: B2 expected 10.0, got None; B3 expected 25.0, got None.

<diagnosis>
LABEL: Compute literals over write-and-save formulas

The SUCCESS-group (rollouts 0 and 2) computed running totals in Python by \
iterating column A with a running sum, and wrote the resulting numbers as \
literal cell values before saving. The FAILURE-group (rollouts 1 and 3) wrote \
=SUM($A$2:A2)-style formulas into column B and saved with openpyxl, which \
writes formula text but does not evaluate it; the checked cells thus contained \
formula strings rather than numbers.

The deciding factor is the choice between writing a formula and computing the \
value. The success approach is robust: it does not depend on whether the save \
path evaluates formulas. The failure approach is fragile: it depends on the \
saving library evaluating formulas, which openpyxl does not.

The skill should learn: when a task evaluates cell values rather than formula \
text, compute the numbers in Python and write them as literals. Formulas are \
only safe when the save path evaluates them, and openpyxl does not.
</diagnosis>

# Example (function-level deciding factor)

Task: "Find the agent's daily score on the Front sheet by matching the date \
in the header row and the agent letter in column A; return the value from \
column F of the Data sheet."
Cell comparison from failed rollout: B2 expected 50, got #N/A.

<diagnosis>
LABEL: 2-criteria INDEX/MATCH array form

The SUCCESS-group built INDEX/MATCH with array-criteria multiplication for the \
two-criteria lookup: \
`=IFERROR(INDEX(Data!$F:$F, MATCH(1, (Data!$A:$A=$A2)*(Data!$B:$B=B$1), 0)), "")`. \
The criteria multiplication produces a 1 where both conditions hold and the \
MATCH(1, ...) finds that row. The FAILURE-group used VLOOKUP or a single-criterion \
MATCH that cannot combine row-and-column conditions, returning #N/A.

The deciding factor is recognizing that two-criteria lookups across distinct \
columns require array-form INDEX/MATCH with criteria multiplication, not \
VLOOKUP or single-criterion MATCH.

The skill should learn the function-level pattern: for two-criteria lookups \
across distinct columns, use \
`=INDEX(target_range, MATCH(1, (criteria_1_range=key_1)*(criteria_2_range=key_2), 0))`, \
wrapped with IFERROR(..., "") for missing matches. The Python equivalent if \
computing literals is to dict-key on a tuple of both criteria: \
`lookup = {(row[k1], row[k2]): row[v] for row in source}`. \
Choose formula form when the task asks for a formula in a cell; choose Python \
literal when the save path does not evaluate formulas.
</diagnosis>

# MUST NOT

- Do not use task-specific values (column letters, cell references, domain \
terms) in the LABEL.
- Do not generalize from the failed-rollout cell comparison alone — read the \
trace files to see how the rollouts actually behaved.
- Do not prescribe specific changes to the skill document; describe what \
knowledge the patcher should write.
- Do not give only abstract workflow advice when the deciding factor is at the \
formula/function level — include the specific syntax.\
"""


ALL_FAIL_CLUSTERING_PROMPT = """\
You analyze K failed executions of the SAME task under the SAME skill artifact. \
The K rollouts differ only in random sampling (no skill version difference). \
Your job is to characterize the failures collectively and produce one diagnosis \
that helps the skill evolve.

You receive: the task description, a cell-by-cell comparison from one rollout \
(the others have similar wrong outputs), and file paths to all K execution traces.

Workflow:

1. Read each trace and identify each rollout's failure mode — the specific way it \
went wrong (which library/approach it chose, which assumption it made, which \
reasoning step it skipped).

2. Determine if the K failures are CONVERGENT or DIVERGENT:
   - CONVERGENT: all K rollouts failed in essentially the same way (same code \
pattern, same wrong assumption, same skipped step). Strong evidence the skill \
needs ONE specific rule.
   - DIVERGENT: rollouts failed in distinct ways (different mistakes, different \
paths to wrong output). Evidence the task class is hard and needs a checklist \
or decision framework, not a single rule.

3. Produce ONE diagnosis tailored to the case.

4. **Match abstraction level to failure mode**: if the convergent failure is a \
*workflow* error (wrong output modality / skipped verification step / wrong \
target sheet), the diagnosis should be process-level. If the convergent \
failure is a *formula or function syntax* error (wrong Excel function chosen, \
wrong formula shape, missing array wrapping, etc.), the diagnosis MUST include \
the correct formula syntax (verbatim Excel formula) AND a Python equivalent if \
literal computation would also work. The skill should learn function-level \
knowledge with concrete syntax — not abstract advice — when the failure is at \
the formula/function level.

Write your analysis inside a <diagnosis> block. Start with a LABEL — a short \
phrase (3-6 words) naming either the general failure type (for convergent) or \
the task-class hardness (for divergent). Then state the CASE explicitly \
(CONVERGENT or DIVERGENT), then write your analysis in plain prose.

For CONVERGENT cases, the prose should describe: the single shared failure \
mode, the reasoning step or check that would have prevented it, and what \
specific knowledge the skill should learn. If the failure is formula-level: \
include the correct Excel formula construction AND the Python equivalent.

For DIVERGENT cases, the prose should describe: the distinct failure modes \
briefly (one sentence each), what they collectively reveal about why this \
task class is hard, and what kind of checklist or decision framework would \
help — not a single rule.

# Example (convergent, process-level)

Task: "Fill column B with the running total of column A values."
Cell comparison from rollout 0: B2 expected 10.0, got None; B3 expected 25.0, got None.

<diagnosis>
LABEL: Unevaluated formula output

CONVERGENT. All 4 rollouts wrote =SUM($A$2:A2)-style formulas into column B \
and saved with openpyxl. openpyxl writes formula text but does not compute it, \
so the checked cells contain formula strings rather than numbers — every \
rollout produced None on read-back. The shared failure: every rollout chose to \
write a formula instead of computing the value, and none stopped to check \
whether the saving library evaluates formulas. The skill should learn that \
when a task evaluates cell values (not formula text), the agent must compute \
numbers in Python and write them as literals — formulas are unsafe under \
non-evaluating save paths.
</diagnosis>

# Example (convergent, function-level)

Task: "Sum amounts from column D using SUMIFS where the Region criteria comes \
from a list in F10:F14 (matching any of the listed regions)."
Cell comparison: F6 expected 30, got #VALUE!.

<diagnosis>
LABEL: SUMIFS does not accept criteria-list

CONVERGENT. All 4 rollouts wrote `=SUMIFS(D:D, A:A, F10:F14)` treating the \
multi-cell range F10:F14 as a list of OR alternatives. SUMIFS does not natively \
accept a multi-cell criteria range as an OR-list — it expects ONE criterion \
per criteria_range argument. Excel evaluates each criterion against the \
corresponding row position rather than as alternatives, producing #VALUE!. \
None of the rollouts wrapped the SUMIFS to aggregate over multiple criteria.

The skill should learn the function-level pattern for OR-criteria SUMIFS: \
wrap with SUM or SUMPRODUCT to aggregate across the criteria list — \
`=SUMPRODUCT(SUMIFS(D:D, A:A, F10:F14))` or `=SUM(SUMIFS(D:D, A:A, F10:F14))` \
(array-entered if necessary). The Python equivalent if computing a literal \
is `df.loc[df['Region'].isin(criteria_list), 'Amount'].sum()`. Choose the \
formula wrapper when the task wants a formula in a cell; choose the Python \
literal when the save path does not evaluate formulas.
</diagnosis>

# Example (divergent)

Task: "Reorganize Sheet2 so that each customer's orders are grouped, sorted \
by date, with running totals appended."
Cell comparison from rollout 0: many cells differ.

<diagnosis>
LABEL: Multi-step transformation underspecified

DIVERGENT. Rollout 0 used pandas pivot but lost the original row order. \
Rollout 1 wrote a VBA macro that openpyxl ignored on save. Rollout 2 wrote \
per-cell values manually but with off-by-one column shifts. Rollout 3 used \
INDEX/MATCH formulas that the saving library did not evaluate. There is no \
single shared mistake — rather, the task requires several independent decisions \
(input layout, library choice, formula-vs-literal, row-identity preservation) \
and each rollout got at least one wrong. The skill should learn a checklist \
for tasks of this shape: (a) inspect the input layout before transforming, \
(b) decide formula-vs-literal based on whether the save path evaluates, \
(c) verify row identity is preserved by reading back the checked cells.
</diagnosis>

# MUST NOT

- Do not use task-specific values (exact column letters, cell references, \
domain terms) in the LABEL — it should make sense for any similar task.
- Do not prescribe specific changes to the skill document; describe what \
the failures reveal and what knowledge would prevent them.
- Do not skip the CASE classification — every diagnosis must say CONVERGENT \
or DIVERGENT.
- Do not give only abstract workflow advice when the failure is at the \
formula/function level — include the correct syntax (Excel + Python).\
"""
