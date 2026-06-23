# Resolve composite cells into the requested answer

Use this procedure when a matched table cell is not atomic: scorelines, paired values, ranges, cells listing multiple alternatives, record fields used for ranking, or cells that pack multiple entities into one row. The goal is to return the component, ranking tuple, or entity set that matches the question's answer type rather than the full cell text.

```python
import re

text = str(cell_value)
parts = [p.strip() for p in re.split(r"\bor\b|/|;|,|\n", text) if p.strip()]
nums = [int(x) for x in re.findall(r"\d+", text)]

if " or " in text.lower() and parts:
    chosen = parts[0]
elif len(nums) >= 2:
    chosen = nums[0]
elif nums:
    chosen = nums[0]
else:
    chosen = text
```

## Branch by cell shape and requested answer type

1. Determine the requested answer type first: scalar number, label, one option from a list, ranking tuple, or individual entities to aggregate.
2. If the cell contains a paired result such as two numbers around a separator, use row context to map the question to the relevant side before returning one number.
3. If the question asks for the best or top entry and the score field is record-like, parse every meaningful numeric part and compare rows on the full tuple with the correct direction for each component.
4. If the cell contains alternatives in one cell, parse each option, compare them against the reference condition, and return only the qualifying option.
5. If the cell contains a range or interval, parse lower and upper bounds before applying comparative language.
6. If the cell contains multiple entities in one displayed cell, split on row-internal separators such as newlines before counting, deduplicating, or taking a frequency statistic.
7. Drop placeholders, blanks, and obvious non-entity filler before aggregation, then normalize whitespace and casing consistently across the split pieces.

## Worked procedure for scorelines, ranking tuples, intervals, and multi-entity aggregation

```python
import re
import pandas as pd

def parse_record_tuple(text):
    nums = [int(x) for x in re.findall(r"\d+", str(text))]
    return tuple(nums)

def parse_interval(text):
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)]
    if len(nums) >= 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        return nums[0], nums[0]
    return None, None

def explode_entities(series):
    pieces = (
        series.fillna("")
        .astype(str)
        .str.split(r"\n|;|/")
        .explode()
        .astype(str)
        .str.strip()
    )
    pieces = pieces[pieces.ne("")]
    pieces = pieces[~pieces.str.fullmatch(r"-|none|n/a", case=False)]
    return pieces

def score_component(score_text, side):
    nums = [int(x) for x in re.findall(r"\d+", str(score_text))]
    if len(nums) < 2:
        return None
    return nums[0] if side == "left" else nums[1]

records = df.copy()
records["rank_key"] = records[score_col].map(parse_record_tuple)
records = records[records["rank_key"].map(bool)]
records["rank_key"] = records["rank_key"].map(lambda t: (t[0], -t[1]) if len(t) >= 2 else t)
best_row = records.sort_values("rank_key", ascending=False).iloc[0]

side = "left" if row_team == asked_team else "right"
points_scored = score_component(cell_value, side)
lower, upper = parse_interval(str(cell_value))
entities = explode_entities(df[target_col])
```

When a result field stores something like `1-0` or `2–3`, do not return the whole scoreline for a question about points, goals, runs, or scores by one side. Use the row context to decide which side of the paired value belongs to the asked team or participant, then return only that scalar component. If the side cannot be grounded from row context, stop and re-check the schema before guessing.

When a record-like field encodes something like wins-losses, choose the per-component direction before sorting. A common pattern is wins descending and losses ascending, which can be represented by a sort key like `(wins, -losses)`. If the domain wording implies another order, encode that order explicitly and compare the full parsed tuple rather than only the first number.

Use `mode == "strict_above"` for wording that requires values above a threshold, and keep boundary-touching intervals separate from intervals entirely above it. A range such as `160–212` reaches the boundary but does not satisfy a strict-above test. When aggregating over packed entities, split first and only then run `value_counts`, `nunique`, or argmax logic on the exploded values.

## Verification

After selecting an answer, verify that its type matches the question: a number for scalar questions, one option for disjunctive cells, a full ranking tuple for record comparisons, a boolean comparison result for interval tests, or a collection of atomic entities before aggregation questions are answered.

```python
def is_single_option(ans):
    s = str(ans)
    return " or " not in s.lower() and "/" not in s and "\n" not in s

if requested_type == "scalar" and not isinstance(answer, (int, float)):
    raise ValueError("expected scalar; re-parse the composite cell for numeric content")
if requested_type == "option" and not is_single_option(answer):
    raise ValueError("expected one option; split alternatives and choose the qualifying entry")
if requested_type == "ranking_tuple" and len(parse_record_tuple(best_row[score_col])) < 2:
    raise ValueError("ranking field still underspecified; parse all score components before comparing rows")
if requested_type == "interval_test" and answer is False:
    raise ValueError("interval failed the comparison; adjust the boundary mode or test another row")
if requested_type == "aggregate_entities" and any("\n" in str(v) for v in entities.head(5)):
    raise ValueError("multi-entity cells remain unsplit; explode row-internal lists before aggregating")
if requested_type == "team_score" and points_scored is None:
    raise ValueError("paired score field not resolved to one side; ground the asked team or participant before returning")
```

If verification fails, do not write the current answer. Re-parse the record into all meaningful components and rebuild the tuple comparator, re-parse the interval endpoints, ground the asked side before selecting one score component, switch between strict-above and inclusive-at-least only if the wording supports it, or explode the packed cells and remove placeholders before recomputing counts on the atomic entities.
