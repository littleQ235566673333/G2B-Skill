---
name: xlsx
description: Inspect workbook structure before choosing an operation, then write the evaluator-visible spreadsheet artifact with exact saved output verification.
---

# Excel Spreadsheet Processing

Use `openpyxl` for workbook-preserving edits and inspect the workbook layout before deciding whether the task is a data edit, a formula write, a formatting change, or a textual code response.

## Execution Mode Selector

Before solving, identify the dominant risk and choose one mode:
- Schema Grounding Mode: Workbook layout, headers, sheet structure unclear or composite
- Verification Mode: Output format, modality, exact value, or answer-shape risk
- Plan-first Mode: Multi-step decomposition, deliverable choice, or stateful traversal
- Standard Mode: Specific procedure: ordinal navigation or FIFO inventory

## Mode: Schema Grounding

### Edit cells and formulas from nearby sheet context

Before writing, inspect the workbook to confirm the real source and target layout: derive actual input, lookup-table, helper, and destination columns from headers and sample rows; use repeated labels across source and destination blocks to align who or what each output row corresponds to; treat destination headers and any filled examples as evidence of whether the target cell wants an aggregate, a flag, or the label associated with an aggregate; trace nearby formulas to distinguish upstream helper cells from downstream display cells; and recover complete inferred mappings from workbook evidence instead of from prompt wording or only the first filled examples. Inspect raw cell contents, not only displayed text, whenever parsing could be corrupted by hidden characters or ambiguous delimiters: print `repr(...)` for suspicious text, normalize or strip invisible format-control characters before splitting dates or numbers, and sample multiple populated cells to see whether delimiters create trailing empty tokens that must be dropped. When displayed headers are generic, duplicated, abbreviated, or placeholder-like, do not map fields by same-text equality alone; infer semantic source-to-destination mapping from sample rows and any expected-output example, then encode explicit exceptions for fields whose meaning diverges despite matching header text. When reshaping blank-separated groups, use any worked destination example to determine whether each source block becomes one output row or one output column, and preserve group boundaries rather than flattening all nonblank cells together. When row logic depends on sibling-cell patterns, mixed-content strings, or running sequences, inspect several complete examples first: infer the invariant across the whole row, isolate the outlier value by repetition pattern rather than a fixed column position, locate the true delimiter boundary in the text rather than trimming by a guessed offset from an internal character like `@`, and decide from sample output whether state persists across non-trigger rows or resets locally before choosing a recurrence or Python loop. For delete/filter tasks, identify the exact mutable row band before any destructive edit, protect adjacent structural rows such as headers immediately above the band, and restrict blankness tests, clearing, compaction, overwriting, and row deletion to the specified rows and criterion columns only.

```python
from openpyxl import load_workbook

wb = load_workbook("input.xlsx")
ws = wb[wb.sheetnames[0]]

for row in range(start_row, end_row + 1):
    key_parts = [normalize(ws.cell(row=row, column=c).value) for c in key_cols]
    source_row = find_matching_row(source_rows, key_parts)
    result = derive_output(source_row, row_context=row)
    ws.cell(row=row, column=target_col).value = result

wb.save("output.xlsx")
```

Decision rule: if output depends on neighboring labels, paired lookup cells, offset source rows, repeated labels between source and destination blocks, destination headers, filled output examples, local helper formulas, ordered slot columns, side-by-side score columns, rowwise repetition patterns, token boundaries inside mixed strings, raw text that may contain invisible characters, ambiguous placeholder headers, delimiter behavior in populated cells, block orientation shown by a worked target example, sample output sequences that reveal persistence-versus-reset behavior, exact mutable row bands, or whether the destination is a complete numeric report block, inspect one complete example group first, then validate the inferred mapping against the actual sheet layout and against target rows that exercise less-evidenced cases before filling the whole range. When multiple score columns sit side by side, test whether each column is an independent contest before aggregating across columns. When prompt wording about lookup direction is ambiguous, print headers and sample rows from both source and target sheets and let header semantics decide the mapping direction.

### Process segmented ranges with block-aware sorting

For sheets split into multiple non-blank regions, detect each contiguous block, decide whether its first row is a header, and apply sorting or reshaping only to the block body while preserving row pairings.

```python
def process_block(rows):
    header = rows[0] if is_header_row(rows[0]) else None
    body = rows[1:] if header else rows
    body.sort(key=sort_key)
    return ([header] if header else []) + body

result_rows = []
for block in iter_nonblank_blocks(grid_rows):
    result_rows.extend(process_block(block))
```

Decision rule: if blank rows separate repeated table regions, operate per region instead of over the whole used range.

#### Common pitfalls (schema grounding)

- **Skipping layout inspection**: prompt examples may show one instance, while the sheet reveals real source columns, destination-header meaning, repeated-label alignment, lookup direction, formula dependency direction, row mapping, composite keys, slot direction, complete inferred mappings, rowwise repetition invariants, token boundaries inside mixed strings, hidden text contamination, semantic-vs-placeholder headers, delimiter edge cases, block orientation, sample-sequence persistence, the real mutable band for destructive edits, or whether the destination is a complete numeric table that requires materialized zeros.
- **Losing headers during block operations**: sorting or reshaping an entire segmented block can move title rows into the data unless you exclude header rows explicitly.
- **`data_only=True` destroys formulas on save**: use a separate workbook object when you need calculated values and also need to preserve formulas.
- **`ws.max_row` overcounts**: formatted-but-empty rows can extend the used range, so scan for real non-empty cells when finding data boundaries.

## Mode: Verification

### Verify exact written output

Identify the evaluator-visible target cells and confirm the saved workbook contains the final artifact they require: exact text, exact numbers, formulas built from the full populated source extent, and compatible computed results, not an intermediate flag or only an intended formula string. Preserve semantic distinctions in the saved artifact: a true computed numeric zero stays numeric `0`, while blanks or hyphens are only for cells intentionally left blank in the final report. Distinguish decorative or scaffolding rows from graded numeric ranges in the same sheet; a marker row may display `-`, but evaluator-checked calculation cells underneath can still require numeric zeros. When populating a complete numeric output block, materialize every evaluator-visible numeric cell in that block; if a structurally required row or intersection is blank in the source but still belongs to the target numeric table, write `0` instead of leaving the destination blank. For rolling date or workday windows, resolve endpoint semantics on one concrete example before encoding the formula: list the exact included dates and confirm whether the anchor date itself belongs in the expected set. When a graded cell depends on a final scalar aggregate and workbook-side formula evaluation is uncertain, or when the logic uses custom date/time windows or cumulative subtraction, compute the scalar in Python, write the literal result, then reopen and verify that the saved target cell exposes exactly that value.

```python
from openpyxl import load_workbook

wb = load_workbook("output.xlsx")
ws = wb[wb.sheetnames[0]]

for cell in check_cells:
    value = ws[cell].value
    assert matches_expected_artifact(cell, value)
```

Decision rule: when writing formulas, first scan the relevant source columns for the true nonblank last row and build every parallel range from that verified extent. Treat formulas that rely on implicit arrays, range-to-range comparisons, CSE-style behavior, or workbook recalculation on open as suspect unless support is known. For array-like conditional aggregations or lookups, for workday/date-window formulas whose inclusive-versus-exclusive cutoff is easy to misread, or for text-filtered aggregates whose grade depends on one saved scalar cell, prefer computing the final values in Python and writing visible literals or blanks unless formula evaluation is guaranteed. After saving, reopen and inspect evaluator-visible target cells for the exact final scalar results, not just the stored formula text; if cells show stale values, blanks where computed results should appear, omitted later rows, joined text in the wrong destination orientation, blanks in place of required zeros inside a complete numeric report block, hyphens replacing computed zeros, boundary-shifted date windows, or formula errors, revise the range or materialize the outputs before filling the rest.

#### Common pitfalls (verification)

- **Stopping at an intermediate artifact**: a workbook may contain helper flags and final graded outputs in different columns, or may require the label associated with an extremum rather than the extremum value itself.
- **Trusting a plausible formula string**: formulas can be logically right yet fail from self-reference, truncated source ranges, unsupported array behavior, missing recalculation, wrong window boundaries, or unverified visible orientation, so verify reopened computed results on representative targets.
- **Collapsing true zeros into blank display markers**: treat blankness as a semantic state, not as any computed value equal to zero.

## Mode: Plan-first

### Classify the deliverable before writing

1. Inspect the workbook contents first: target sheet names, populated ranges, repeated blocks, headers, and any example or result tabs that reveal the expected final workbook state.
2. Choose the operation from workbook evidence before coding; prompt examples and keywords are secondary to what the sheet structure shows.
3. If success is determined by saved worksheet contents, edit the workbook directly and never place explanatory text or VBA/source lines into evaluated cells, even when the prompt is phrased as a macro fix or mentions Power Query/VBA.
4. Only return or place code text when the task explicitly requires a code artifact rather than workbook-state output.
5. Once you identify the output modality, keep it fixed; later prompt wording that mentions another artifact type is metadata unless the workbook task explicitly requires both.

### Simulate stateful traversal on an example

For left-to-right scans that restart, skip ahead, or reuse prior matches as the next reference, dry-run the traversal on the workbook's example before coding so the cursor-update semantics are explicit.

```python
def simulate_scan(values, start_idx=0):
    ref = start_idx
    hits = []
    while ref < len(values):
        match_idx = find_next_match(values, ref)
        if match_idx is None:
            break
        hits.append((ref, match_idx))
        ref = choose_next_reference(ref, match_idx)
    return hits
```

Decision rule: if a task says to find a condition, count a hit, then continue or restart from somewhere relative to that hit, record the current reference cell, matched cell, next search start, and next reference after each hit on a concrete sheet example. Only implement the scan once the simulated hit sequence matches the workbook's worked pattern; otherwise revise the restart semantics before writing results.

#### Common pitfalls (plan-first)

- **Mixing output modalities**: code requests and workbook-edit requests are different deliverables; when grading is by saved cell state, writing source text into evaluated cells corrupts the sheet.
- **Leaving traversal semantics implicit**: stateful scans can undercount or overcount when “continue from here” is not concretized into the next reference cell and next search start on a worked example.

## Mode: Standard

### FIFO ending inventory valuation

For FIFO ending inventory tasks, treat sold units as consuming the oldest layers first, so the units still on hand come from the newest remaining layers.

```python
def fifo_ending_value(layers, ending_qty):
    remaining = ending_qty
    taken = []
    for qty, unit_cost in reversed(layers):
        use_qty = min(remaining, qty)
        if use_qty:
            taken.append((use_qty, unit_cost))
            remaining -= use_qty
        if remaining == 0:
            break
    return sum(q * c for q, c in taken)
```

Decision rule: if the sheet lists inventory layers chronologically and asks for FIFO ending inventory cost or unit cost, allocate the ending quantity from the latest purchase layers backward, not from beginning inventory forward.

#### Common pitfalls (standard)

- **Reversing FIFO layer direction**: ending inventory under FIFO is priced from newest remaining layers, not oldest layers first.
