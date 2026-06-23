# SS mapping: original SKILL.md → SKILL_mode_selector.md

Source: `results/runs/g2b-v8_gpt-5.4/skills/xlsx/SKILL.md` (197 lines)
Output: `analysis/precheck_a/SS_mode_selector.md` (222 lines)
Generation: `scripts/precheck_a_split_ss.py` (deterministic slice + reorganize)

## Audit summary

| Constraint | Status |
|---|---|
| 不新增 rule | ✓ — script validates: every non-header source line present in output verbatim |
| 不删除 rule | ✓ — all 10 main sections + Common Pitfalls preserved; FIFO/Navigate procedure code blocks intact |
| 不改写措辞 | ✓ — section bodies copied byte-identical; only header levels demoted (## → ###) to nest under Mode H2 |
| trigger ≤15 token/条 | ✓ — 4 trigger sentences each within 15 tokens (longest: "Multi-step decomposition, deliverable choice, or stateful traversal" = 8 tokens) |
| 不造新 mode | ✓ — exactly 4 modes per brief |

**New text introduced**: 1 mode-selector intro block (5 lines: H2 header + intro sentence + 4 trigger lines) + 4 Mode H2 headers + 4 Common-pitfalls H4 headers. ~13 new structural lines vs 197 source lines = ~6.6%. Under 10% threshold.

## Section → mode mapping

| Source section | Mode | Rationale |
|---|---|---|
| Classify the deliverable before writing | Plan-first | Workflow ordering: schema → choose modality → output format. Decides task type before coding. |
| Match question intent before aggregating or copying | Verification | Answer-shape classification: count vs single vs cell. Validates output shape. |
| Decompose compositional questions into column predicates | Plan-first | Multi-step decomposition into predicates; conjunction over columns. |
| Edit cells and formulas from nearby sheet context | **Schema Grounding** ⚠️ | Largest section. Borderline cross-cutting (also has plan/verification content), but dominant intent is "infer from workbook evidence" → schema. Per brief: kept whole, no split-rewrite. |
| Extract atomic answers from composite cells | Verification | Output-side parsing: select correct component to emit. |
| Navigate next/previous values in sparse columns | Standard | Specific procedure for ordinal navigation. |
| Simulate stateful traversal on an example | Plan-first | Dry-run/simulate before coding; explicit cursor-update planning. |
| Process segmented ranges with block-aware sorting | Schema Grounding | Detect block layout, decide header rows. Sheet-structure inference. |
| Verify exact written output | Verification | Reopen and check evaluator-visible target cells. |
| FIFO ending inventory valuation | Standard | Specific domain procedure. |

## Common Pitfalls bullet → mode

| Bullet (substring) | Mode |
|---|---|
| Skipping layout inspection | Schema Grounding |
| Matching the wrong answer shape | Verification |
| Collapsing multi-column semantics into one filter | Plan-first |
| Mixing output modalities | Plan-first |
| Leaving traversal semantics implicit | Plan-first |
| Treating blank spacer rows | Standard |
| Losing headers during block operations | Schema Grounding |
| Stopping at an intermediate artifact | Verification |
| Trusting a plausible formula string | Verification |
| Collapsing true zeros into blank display markers | Verification |
| Reversing FIFO layer direction | Standard |
| `data_only=True` destroys formulas on save | Schema Grounding |
| `ws.max_row` overcounts | Schema Grounding |

## Mode load distribution

| Mode | # sections | # pitfall bullets | Total items |
|---|---|---|---|
| Schema Grounding | 2 | 4 | 6 |
| Verification | 3 | 4 | 7 |
| Plan-first | 3 | 3 | 6 |
| Standard | 2 | 2 | 4 |

Total: 10 main sections + 13 pitfalls = 23 substantive items, distributed as 6/7/6/4 across modes. Roughly balanced; no mode dominates >30%, no mode under 15%.

## Cross-cutting flag (informational, not a stop trigger)

The "Edit cells and formulas from nearby sheet context" section (paragraph at L57 in source, L22 in output) contains rules that span 3 modes:
- Schema content (dominant): "inspect workbook to confirm real source/target layout", "trace nearby formulas", "infer semantic mapping from sample rows"
- Plan content: "decide whether each source block becomes one output row or one output column", "infer the invariant across the whole row before choosing a recurrence or Python loop"
- Verification content: "identify the exact mutable row band before any destructive edit", "protect adjacent structural rows"

Per brief constraint, this section is kept whole (assigned to dominant mode = Schema Grounding) rather than split. This is the only cross-cutting section in the SS skill. It would be a stop trigger if there were ≥3 such sections; with 1, we proceed but flag it for the eval reader.

## Pre-execution stop check (passed)

- Cross-cutting (rule in ≥3 modes): 1 section ("Edit cells..."). Brief threshold was qualitative ("大量 cross-cutting"); 1/10 = 10% is borderline but not "大量". Proceed with flag.
- Standard share: 4/23 = 17%. Under 30% threshold ✓
- New connective text: ~6.6% structural additions. Under 10% threshold ✓

All gates pass with the cross-cutting note. Mode-selector form is a clean reorganization of the SS skill.
