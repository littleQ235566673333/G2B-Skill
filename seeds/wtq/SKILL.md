---
name: wtq
description: Use this skill whenever the user asks a question about a CSV-formatted table (WikiTableQuestions style). The task is to read the table, compute the answer to a natural-language question, and write the answer(s) to output.txt — one answer per line.
---

# Table-question answering

Use `pandas` to read the CSV; compute the answer in Python; write the answer string(s) to `output.txt`, one answer per line. Multi-answer questions are common — emit one line per item.

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

- The question is in plain English. Identify which column(s) it queries and which condition(s) constrain rows.
- Some questions ask for **one** answer (e.g., "what was the last year ..."), others ask for **a set** (e.g., "which countries ..."). Read carefully — emitting one answer for a set-question, or vice versa, will fail.

## Common Pitfalls

- **Numbers stored as strings**: `df["Year"]` may be string `"2004"`, not int `2004`. Cast before numeric comparison: `df["Year"].astype(int)` or compare to string.
- **Whitespace and case**: cell values may have trailing whitespace or inconsistent case. Use `.str.strip()` and `.str.lower()` when matching.
- **Empty / missing cells**: `pd.read_csv` represents empty cells as `NaN`. Filter with `.dropna()` or `.fillna("")` as appropriate.
- **Header detection**: most WTQ tables have a header row, but a few have multi-row headers or no header. If the first row looks like data, pass `header=None` and assign columns manually.
- **Output format**: write the **literal answer string** as it would appear in the table — don't paraphrase, don't add units the question didn't ask for, don't wrap in quotes.
- **Sorting / aggregation**: questions like "what was the last X" require explicit sort + selection, not just `.iloc[-1]` (which assumes data is already in order).
