---
name: wtq
description: Use this skill whenever the user asks a question about a CSV-formatted table (WikiTableQuestions style). The task is to read the table, compute the answer to a natural-language question, and write the answer(s) to output.txt — one answer per line.
---

# Table-question answering

Use `pandas` to read the CSV; compute the answer in Python; write the answer string(s) to `output.txt`, one answer per line. Multi-answer questions are common — emit one line per item.

## Mandatory First Action

**Your VERY FIRST action on any WTQ task MUST be a shell call that prints
the question text, the table's columns, the first 5 rows, and the row
count.** Do not skip. Do not "plan first then act" — print first, then
plan from real data.

```python
python3 -c "import pandas as pd; \
df = pd.read_csv('input.csv'); \
print('shape:', df.shape); \
print('columns:', list(df.columns)); \
print(df.head())"
```

(The question text is provided in the task instruction; reread it.)

This gives you: number of rows, exact column names (with spaces /
casing / punctuation as in the table), and value samples so you can
identify dtypes (string vs numeric vs date). EVERY downstream filter /
sort / group decision depends on this output.

## Workflow: Identify Question Type Before Coding

After printing structure, classify the question into one of these types
EXPLICITLY before writing any code:

1. **lookup** — "what was the score of team X in year Y?" → filter rows by conditions, return one value
2. **count** — "how many ... ?" → filter rows, return `len()`
3. **min/max** — "who scored the most ... ?" → sort + iloc[0] or `.idxmax()`
4. **first/last** — "what was the first ... ?" → sort by date/year, take iloc[0] or [-1]
5. **set membership** — "which countries had ... ?" → filter, list unique values, one per line
6. **comparison** — "did X have more than Y?" → compute both, compare, output yes/no
7. **aggregate** — "total points scored?" → sum or mean over filtered rows
8. **before/after** — "what came right after X?" → sort, find index of X, take next

Different types need different code patterns. Misidentifying the type
is the #1 cause of WTQ failures.

## Quick Start

```python
import pandas as pd

df = pd.read_csv("input.csv")
# df columns are strings; values are strings (default); cast as needed.

answer = df.loc[df["Year"] == 2004, "Team"].iloc[0]

with open("output.txt", "w", encoding="utf-8") as f:
    f.write(str(answer) + "\n")
```

For multi-answer questions, write each answer on its own line:

```python
matches = df.loc[df["Country"] == "Italy", "Player"].tolist()
with open("output.txt", "w", encoding="utf-8") as f:
    for m in matches:
        f.write(str(m) + "\n")
```

## Reading the question carefully

- The question is in plain English. Identify which column(s) it queries
  and which condition(s) constrain rows.
- Some questions ask for **one** answer (e.g., "what was the last year ..."),
  others ask for **a set** (e.g., "which countries ..."). Read carefully —
  emitting one answer for a set-question, or vice versa, will fail.

## Output Format Verification

After writing `output.txt`, **re-read it and verify** the format matches
what the question expects:

```python
with open("output.txt") as f:
    print(repr(f.read()))
```

Check:
- One answer per line
- No trailing whitespace or extra blank lines
- Answer is the **literal string** as it appears in the table (don't
  paraphrase, don't add units the question didn't ask for, don't wrap
  in quotes)
- For set-questions, count of lines matches expected count

## Common Pitfalls

- **Numbers stored as strings**: `df["Year"]` may be string `"2004"`, not int `2004`. Cast before numeric comparison: `df["Year"].astype(int)` or compare to string.
- **Whitespace and case**: cell values may have trailing whitespace or inconsistent case. Use `.str.strip()` and `.str.lower()` when matching.
- **Empty / missing cells**: `pd.read_csv` represents empty cells as `NaN`. Filter with `.dropna()` or `.fillna("")` as appropriate.
- **Header detection**: most WTQ tables have a header row, but a few have multi-row headers or no header. If the first row looks like data, pass `header=None` and assign columns manually.
- **Output format**: write the **literal answer string** as it would appear in the table — don't paraphrase, don't add units the question didn't ask for, don't wrap in quotes.
- **Sorting / aggregation**: questions like "what was the last X" require explicit sort + selection, not just `.iloc[-1]` (which assumes data is already in order).
- **Question-type misidentification**: a question that says "name the players ..." is set-membership (multi-line), not lookup (single-line). Use the §Workflow classification before coding.
