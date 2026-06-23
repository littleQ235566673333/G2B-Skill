---
description: Answer spreadsheet questions by inspecting table structure, grounding question phrases to observed schema, and applying the matching lookup, count, sequence, or comparison operation before returning the denotation the question asks for.
---

## Execution Mode Selector

Before solving, identify the dominant risk and choose one mode:
- Schema Grounding Mode: Column meaning, row scope, or table layout uncertain
- Verification Mode: Output shape: cardinality, denotation type, or composite parse
- Plan-first Mode: Comparison vs adjacency, or repeated-entity relation check
- Standard Mode: Direct count or sequence-step on a clear column

## Mode: Schema Grounding

### Inspect structure before choosing an operation

- Read the sheet into a dataframe and print columns plus a small preview before assuming field names, row meaning, row scope, cell granularity, displayed ordering, or answer shape.
- Infer what one row represents from the table contents, then classify the question as lookup, count, sequence step, comparison, or span rendering before writing code.
- Bind question phrases to observed column values, row subsets, displayed order, and value families in the current sheet; prefer the table's actual labels over generic synonyms, and use representative values to decide whether variants belong to the same class.
- Before any count, latest, earliest, top, or threshold test, determine which rows instantiate the asked unit, whether repeated rows duplicate the same event, whether target cells contain one entity or a row-internal list of entities, and whether repeated category rows must be combined instead of read one by one.
- For count questions, state the aggregation unit explicitly before tallying: qualifying rows, distinct entities, exploded sub-entities from packed cells, or an aggregate over repeated rows for one category.
- After finding matching rows, re-read the interrogative head and choose among returning the matched values, returning one unique denotation shared across matches, and returning the number of matches; phrases like "how many" or "what is the number of" require a count, while singular prompts require a uniqueness check before emitting row-level values.
- For presentation or markup semantics, decide whether the asked property is explicitly represented, only partially proxied, implicitly recoverable from named entities, or not recoverable from the flattened table before filtering or counting.
- When an asked attribute is absent from the schema, use reliable entity-to-attribute inference only for well-known, unambiguous entities; otherwise treat the property as ungrounded rather than guessing.
- After locating the target row or computing a result, choose the output field whose values read like direct answers to the question, and reject IDs, ordinals, codes, headers, and composite display strings unless the question explicitly asks for them.
- If the answer is embedded in prose, return the minimal complete literal phrase from the table that answers the question rather than a shortened head word or paraphrase.
- Verify that the final rendered answer matches the question's denotation type and cardinality, such as a title for "what episode," a number plus unit words for derived measures like age or duration, one scalar component from a structured result cell, one value for a singular prompt, or a year span for "consecutive years."
- Before writing any string answer, check whether it still looks like a serialized representation with escape artifacts or wrapper quotes; de-escape it to the clean literal table value and keep only the intended punctuation.
- When later prompt wording suggests a different category, treat it as metadata unless the table evidence supports changing the operation.

```python
import pandas as pd

df = pd.read_excel(path)
print(df.columns.tolist())
print(df.head())
row_meaning = "entity"  # or event / ranking entry / result row
query_type = "count"  # or lookup / sequence / comparison / span
answer_kind = "label"  # or scalar / duration / year span / identifier
```

Read references/schema_grounding.md when question wording refers to table-specific labels, row meaning, row scope, duplicate events, repeated category rows, multi-entity cells, displayed ordering, encoded values, hidden formatting, implicit-but-recoverable attributes, free-text answer spans, answer cardinality, or answer-field selection. Skip when the target condition and output column are both literal and unambiguous from one column.

#### Common pitfalls (schema grounding)

- Mapping a condition to the wrong similarly named column instead of the column that expresses the asked event or attribute.
- Guessing generic labels, row scope, aggregation unit, displayed ordering, markup semantics, implicit recoverability, exact variants, or hidden multiplicity from remarks instead of checking the observed schema for the table's actual vocabulary, row meaning, duplicate-event structure, repeated category rows, packed entities, recoverable properties, in-scope rows, and presented order.
- Treating parenthetical day tags or similar row-internal annotations as extra records even though the row already represents the counted event or entity.

## Mode: Verification

### Derive a scalar from a composite cell

When the matched cell stores a formatted result such as a scoreline, range, record, or other structured text, parse the cell and return the requested component or numeric quantity instead of copying the whole string.

```python
import re

text = str(cell_value)
parts = [int(x) for x in re.findall(r"\d+", text)]
answer = parts[0] if parts else None
```

Decision rule: if the question requests a single number or ranking signal but the source cell contains multiple embedded values or separators, parse before returning.

Read references/composite_cells.md when the candidate cell contains multiple alternatives, paired values, comparison text, record-like score fields used for ranking, scorelines whose requested side must be selected from row context, or multiple entities packed into one cell. Skip when the matched cell is already the exact atomic answer.

### Collapse consecutive years into a span

When the question asks for consecutive years, collect the matching years, sort them, merge adjacent years into maximal contiguous runs, and return the run as one range string rather than separate year values. Ground the entity filter to observed table variants before collapsing the years.

```python
years = sorted(set(int(y) for y in matched_years))
runs = []
start = end = years[0]
for y in years[1:]:
    if y == end + 1:
        end = y
    else:
        runs.append((start, end))
        start = end = y
runs.append((start, end))
answer = f"{runs[0][0]}–{runs[0][1]}" if runs[0][0] != runs[0][1] else str(runs[0][0])
```

Decision rule: use span rendering for prompts like "what consecutive years" and keep atomic-year output for ordinary "which years" questions.

#### Common pitfalls (verification)

- Returning an identifier, ordinal, code, or header from the right row when the question asks for a descriptive table value.
- Returning a bare intermediate number when the question asks for a typed denotation such as a duration with units.
- Returning a shortened head word when the table text contains a longer literal answer phrase.
- Returning separate year atoms when the question asks for one consecutive-year span.
- Returning a cell from one matched row when the question actually asks for a count of matching rows, a count of distinct entities, an aggregate across repeated category rows, or one unique denotation shared by multiple matching rows.
- Returning raw cell text when the question asks for one numeric component implied by that text.
- Returning multiple candidates to a singular question instead of re-checking for a missed constraint or ambiguity.
- Returning serialized string text with backslashes or wrapper quotes instead of the clean literal answer.

## Mode: Plan-first

### Compute comparisons over entities, not table adjacency

Treat row order as non-semantic unless the question explicitly mentions previous, next row, neighboring column, or another structural relation. For comparative phrases tied to a named entity, identify the reference row, exclude or compare against it as requested, normalize the measure, and compute the global argmax or argmin over the valid rows.

```python
import re

others = df[df[name_col] != reference_name].copy()
others[metric_col] = others[metric_col].astype(str).str.extract(r"([\d.]+)").astype(float)
answer = others.sort_values(metric_col, ascending=False).iloc[0][name_col]
```

Decision rule: when phrasing like "next to" or "beside" names an entity and no structural neighborhood is specified, test the comparison or exclusion reading before any adjacency reading.

### Match repeated entities with explicit relation checks

When the same entity appears across multiple rows, seasons, or categories, translate phrases like "also played in," "later," or "during" into an explicit relation test before computing the answer. Validate the time or category constraint on the paired occurrence instead of taking a raw intersection of column values.

```python
matches = []
for _, row in df.iterrows():
    if relation_holds(row, reference_set, time_window):
        matches.append(row[target_col])
answer = sorted(set(matches))
```

Decision rule: if an entity can recur across rows, require a row-aware or time-aware relation check before using set overlap.

#### Common pitfalls (plan-first)

- Treating repeated-entity questions as raw set intersection without checking the stated time, season, or category relation.
- Treating informal comparative phrasing as row adjacency even though the table order has no semantic role.

## Mode: Standard

### Count qualifying records

Filter rows that satisfy the textual or numeric conditions, then count records when the question asks how many entries meet those conditions. Count only rows that instantiate the asked unit, not headers, totals, section labels, compilations, or later out-of-scope sections that share the same column.

```python
mask = df[text_col].astype(str).str.contains(term_a, case=False, na=False)
mask &= df[other_col].astype(str).str.contains(term_b, case=False, na=False)
answer = int(mask.sum())
```

Decision rule: if one row represents one entity or event and the question asks "how many" or "how many times," count matching in-scope rows before attempting any row lookup.

### Follow next or previous valid entries

For sequence questions, first identify the ordering dimension named or implied by the question, then move to the adjacent item on that dimension before reading the requested field. When wording like previous, next, before, or after refers to a ranked or already ordered table, ground it to the displayed row order before attempting arithmetic on a rank column.

```python
ordered = df.reset_index(drop=True)
pos = ordered.index[ordered[key_col] == key_value][0]
step = -1 if direction == "previous" else 1
neighbor = ordered.iloc[pos + step]
answer = neighbor[target_col]
```

Decision rule: when the question asks for previous, next, above, below, before, or after, default to adjacency on the presented or explicitly requested order; use numeric rank arithmetic only when the question asks about the rank value relation itself.

#### Common pitfalls (standard)

- Treating previous or next as a status-filtered search or numeric-rank arithmetic when the question only names an ordering relation in the presented table.
