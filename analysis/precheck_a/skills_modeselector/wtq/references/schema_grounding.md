# Ground question wording in observed schema and answer type

Use this procedure when the question relies on table-specific labels, row semantics, section boundaries, duplicate records, repeated category rows that may need aggregation, multi-entity cells, encoded values that need normalization, presentation semantics that may have been flattened away, implicitly recoverable attributes from named entities, free-text answer spans, answer cardinality, ranked-table ordering, or when multiple columns could supply the final answer. The goal is to bind the question to evidence present in the table before filtering, counting, selecting a latest row, following previous or next wording, or returning a field.

```python
import pandas as pd

preview = df.head()
value_map = {
    col: df[col].dropna().astype(str).head(8).tolist()
    for col in df.columns
}
print(preview)
print(value_map)
```

## Branch by how the asked property appears in the table

1. List the candidate columns for each question phrase, then inspect representative values before choosing one.
2. State what one row represents before choosing an operation: one entity, one event, one ranked entry, one final, one season row, or another unit.
3. Determine row scope before aggregation or comparison: identify the rows that instantiate the asked unit, and exclude headers, subtotal or total rows, average rows, compilation rows, and later out-of-scope sections that share the same columns.
4. Before counting or taking an argmax, state the aggregation unit explicitly: one raw row, one distinct event after deduplicating repeated records, one atomic entity after splitting packed cells, one distinct person across repeated service rows, or an aggregate across repeated rows for the same category.
5. If the concept is expressed by table vocabulary, match the observed value family rather than a guessed synonym; treat close variants as one class only after seeing them in the data.
6. If a categorical value encodes extra context in the same cell, normalize to the asked entity before aggregating. For example, strip a leading venue marker such as `@` only when the question is about the underlying team rather than home or away status.
7. If the asked property is not explicitly tabulated, branch explicitly: use reliable common background knowledge only for well-known, unambiguous named entities, and otherwise leave the property ungrounded instead of inventing an attribute.
8. For count questions over winner, roster, result, or office-holder cells, separate entity names from score text or other narrative filler before nationality filters, distinct counts, or frequency tallies.
9. If the question asks for a count or for the latest or earliest instance, check whether that operation applies to rows directly, to deduplicated events, to exploded sub-entities, to distinct entities consolidated across repeated rows, or to repeated category rows that must be combined.
10. After filtering qualifying rows, decide whether the prompt asks for the matched values, one unique value shared across those rows, or `len(matches)`; descriptive text conditions still feed a count when the interrogative head is "how many" or "what is the number of."
11. For positional wording such as top, bottom, first, or last, ground the phrase to in-scope data rows unless the question explicitly asks about headers or schema metadata.
12. For sequence wording such as previous, next, before, or after on ranking tables, inspect whether the table is already presented in the relevant order and navigate to the adjacent row in that displayed order before doing arithmetic on rank values.
13. After locating the row or rows, compare candidate output columns and choose the one whose values read like direct denotations of the question rather than IDs, indices, codes, headers, or composite display strings.
14. Before returning, render the result in the answer type implied by the question, such as a label, scalar, number plus unit words for a derived measure, minimal complete literal phrase from prose, clean de-escaped string text, one scalar component from a scoreline, or consecutive-year span.
15. After computing candidate answers, compare their count with the question form: a singular prompt should leave one value, while multiple survivors are only acceptable when they collapse to one unique denotation; otherwise they signal ambiguity, a missed constraint, or an unresolved tie.
16. If row-internal notes, parenthetical day tags, or similar qualifiers appear inside one row, treat them as descriptive unless the question explicitly asks to expand them into separate per-note or per-day records.

## Worked procedure for row scope, aggregation unit, displayed order, and answer-field selection

```python
def looks_like_identifier(series):
    sample = [str(x).strip() for x in series.dropna().head(6)]
    return bool(sample) and all(s.isdigit() or len(s) <= 4 for s in sample)

def normalize_category(text):
    s = str(text).strip()
    return s[1:] if s.startswith("@") else s

def plausible_entity_inference(values):
    sample = [str(x).strip() for x in values if str(x).strip()]
    return bool(sample) and len(sample) <= 8

row_meaning = "event"
if any("rank" in c.lower() for c in df.columns):
    row_meaning = "ranked entry"
elif any("outcome" in c.lower() for c in df.columns):
    row_meaning = "result row"

scope_mask = ~df[name_col].astype(str).str.contains(
    r"total|subtotal|average|header|collection|special|best of",
    case=False,
    na=False,
)
working = df[scope_mask].copy()
working[key_col] = working[key_col].map(normalize_category)

if row_meaning == "event":
    working = working.drop_duplicates(subset=event_key_cols)

if asks_for_entity_count:
    entities = (
        working[source_col].fillna("").astype(str)
        .str.split(r"\n|;|/")
        .explode()
        .astype(str)
        .str.strip()
    )
    entities = entities[entities.ne("")]
    entities = entities[~entities.str.contains(r"\d+-\d+|\d", regex=True, na=False)]

if asks_for_person_count:
    qualifying = working[row_mask].copy()
    answer = qualifying[person_col].astype(str).str.strip().nunique()

if asks_for_category_total and working[match_col].astype(str).eq(match_value).sum() > 1:
    category_rows = working[working[match_col].astype(str) == str(match_value)]
    candidate_values = category_rows[value_col].astype(str)
    if not pd.to_numeric(candidate_values, errors="coerce").notna().all():
        answer = len(category_rows)

if asks_sequence and row_meaning == "ranked entry":
    ordered = working.reset_index(drop=True)
    pos = ordered.index[ordered[key_col].astype(str) == str(key_value)][0]
    step = -1 if direction == "previous" else 1
    answer = ordered.iloc[pos + step][target_col]

condition_col = next(
    (c for c in working.columns if working[c].astype(str).str.contains(target_term, case=False, na=False).any()),
    None,
)

if condition_col is None and plausible_entity_inference(working[name_col].head(6)):
    inferred_ok = True
else:
    inferred_ok = False

target_rows = working.loc[row_mask].copy()
candidate_answers = target_rows[answer_col].astype(str).str.strip().tolist()
unique_answers = sorted(set(a for a in candidate_answers if a))
if asks_singular and len(unique_answers) == 1:
    answer = unique_answers[0]
else:
    target_row = target_rows.iloc[0]
    answer_candidates = [c for c in working.columns if c != condition_col]
    label_cols = [c for c in answer_candidates if not looks_like_identifier(working[c])]
    answer_col = label_cols[0] if label_cols else answer_candidates[0]
    answer = str(target_row[answer_col]).strip()
```

If a chart, ranking, or titled list contains a numeral in its name, do not treat that numeral as the answer unless the question explicitly asks for the list's nominal size. Count or select using the rows that actually satisfy membership in that named list.

If the table is a results-history table, do not assume a phrase like "last title" means "latest row with a winning outcome" until the row semantics support that equivalence. A finals table can mix wins and losses while still not being a direct list of titles.

If the whole table is about one subject but the rows mix regular instances with aggregates, specials, or compilations, do not let the table-level subject override row-level scope. Filter to the rows that actually instantiate the asked unit before applying numeric comparisons or counts.

If repeated rows share the same category and the question asks for how many of that category, do not copy one visible placeholder cell from the matched rows. Aggregate over the matched row set, especially when the apparent answer field is duplicated or non-numeric text.

If a person or office-holder appears in multiple rows for separate terms or stints, do not let row count stand in for person count. First test which rows qualify, then collapse to distinct names before answering questions about how many people.

If descriptive notes or remarks mention quantities, treat them as row annotations unless the question explicitly asks about the quantity stated in prose. When a row already represents the counted event or entity, do not expand parenthetical weekday tags or similar qualifiers into extra records.

If positional wording asks what is at the top or bottom of the table, return the value from the first or last in-scope data row in the relevant column, not the column header.

If sequence wording asks for a ranked item previous or next to another named item, prefer adjacent-row navigation in the table's presented order. Rank values may increase downward, decrease downward, skip numbers, or be nonnumeric, so arithmetic on the rank field is only safe when the question explicitly asks about rank numbers.

If the answer is embedded in notes or another prose field, return the minimal complete literal phrase from that text. For example, preserve a source span like `baroque style` rather than compressing it to `baroque`.

If the extracted answer string still contains backslashes, escaped quotes, or wrapper quotes introduced by parsing, normalize it to the clean literal value before returning it.

## Verification

```python
answer_text = str(answer).strip()
if condition_col is None and not inferred_ok:
    raise ValueError("condition not grounded in any recoverable table field; re-inspect schema, entities, and proxies")
if answer_text == "":
    raise ValueError("empty answer field; compare alternative output columns on the same row")
if asks_for_label and looks_like_identifier(df[[answer_col]].iloc[:, 0]):
    raise ValueError("identifier-like answer for a label question; switch to a descriptive output column")
if asks_for_label and answer_col == condition_col:
    raise ValueError("returned the condition field instead of the requested denotation; compare other columns on the matched row")
if asks_for_duration and not any(unit in answer_text.lower() for unit in ["year", "month", "day", "hour"]):
    raise ValueError("derived measure missing units; format the computed magnitude with the question's time unit")
if asks_for_literal_phrase and answer_text != source_span_text:
    raise ValueError("answer span was shortened or paraphrased; return the minimal complete phrase from the source text")
if asks_for_count and len(working) == len(df):
    raise ValueError("row scope untested; re-check for headers, totals, averages, compilations, or later sections before counting")
if asks_for_count and repeated_category_matches and not used_group_aggregation:
    raise ValueError("matched repeated category rows without aggregation; combine the in-scope row set instead of copying one cell")
if asks_for_entity_count and any(entities.str.contains(r"\d", na=False)):
    raise ValueError("entity list still contains score text or numeric filler; separate names from non-entity text before counting")
if asks_for_person_count and answer != qualifying[person_col].astype(str).str.strip().nunique():
    raise ValueError("counted qualifying rows instead of distinct people; collapse repeated person rows before returning")
if asks_for_count and asks_from_text_condition and answer != len(matches):
    raise ValueError("filtered the right text-matching rows but did not return their count; switch from row lookup to len(matches)")
if asks_row_level_count and expanded_row_internal_annotations:
    raise ValueError("expanded row-internal qualifiers into extra records; return to counting qualifying in-scope rows")
if looks_serialized and cleaned_answer == answer_text:
    raise ValueError("string still looks serialized; de-escape quotes and strip wrapper artifacts before returning")
if asks_singular and len(unique_answers) > 1:
    raise ValueError("singular question left multiple distinct denotations; re-read for a missed constraint or tie rule")
if asks_sequence and row_meaning == "ranked entry" and used_rank_arithmetic_without_order_check:
    raise ValueError("sequence wording was grounded to rank arithmetic instead of displayed order; navigate by adjacent row first")
```

If verification fails, do not write the current answer. Re-inspect representative column values, restate what one row means, then change the operation: narrow the row scope before aggregating, deduplicate repeated event records, split packed multi-entity cells before counting, separate names from score text, count distinct people rather than repeated service rows, aggregate across repeated category rows when direct cells are placeholders, switch from matched values to `len(matches)` for count prompts, collapse multiple matching rows to one shared denotation only when the evidence supports one unique answer, ignore descriptive remarks unless the question targets prose quantities, refuse unsupported expansion of row-internal qualifiers into new records, normalize encoded category markers before tallying, follow displayed order for ranked previous or next wording, switch from unsupported guessing to an explicit ungrounded judgment, return a data-row value instead of a header, preserve the full literal phrase from prose, clean serialized string artifacts, or resolve the singular-versus-multiple candidate mismatch before returning.
