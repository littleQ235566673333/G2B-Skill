---
name: officeqa
description: Use this skill whenever the user asks a grounded reasoning question over U.S. Treasury Bulletin documents (or similar parsed-PDF financial corpora) and provides a directory of source text files. The task is to identify the relevant document(s) and section(s), extract the precise numerical or named answer, and write it to output.txt — one line, no formatting.
---

# Document-grounded reasoning QA

The input is a `sources/` directory of plain UTF-8 text files parsed from
historical PDFs. Files contain a mix of dense financial tables (often
multi-column, comma-separated within cells) and narrative paragraphs.
Each task references a small subset of files (typically 1-5).

The output goes to `output.txt`: one line, the literal answer.
- Numerical answers: digits only — no `$`, no commas, no `million/billion`
  in words. The grader does fuzzy match within ~1% relative error.
- Non-numeric answers: the short literal phrase (named entity, date
  range, etc.).

## Quick Start

```python
from pathlib import Path

# 1. List sources
src_files = sorted(Path("sources").iterdir())
print(f"Source files: {[f.name for f in src_files]}")

# 2. Read all of them (or grep for keywords first if files are large)
texts = {}
for f in src_files:
    if f.is_file():
        texts[f.name] = f.read_text(encoding="utf-8", errors="replace")

# 3. Search for keywords from the question
import re
question_keywords = ["federal debt", "1942"]
for name, txt in texts.items():
    for kw in question_keywords:
        for m in re.finditer(re.escape(kw), txt, flags=re.IGNORECASE):
            start = max(0, m.start() - 200)
            end   = min(len(txt), m.end() + 200)
            print(f"\n[{name}] @{m.start()}: ...{txt[start:end]}...")

# 4. Extract the number
# … reasoning here …

# 5. Write the answer
answer = "72422000000"   # digits only — no $, no commas
Path("output.txt").write_text(answer + "\n", encoding="utf-8")
```

## Strategy that works well

1. **Skim file names first**, not contents. Treasury Bulletin parses are
   often named by date / quarter / page — picking the right file by name
   prunes 80% of the search space before reading any content.

2. **Grep with keywords from the question**, not the full text. Questions
   reference specific years, fund names, accounts — those are searchable
   strings.

3. **For tabular data**, the text-parse usually preserves column
   alignment with whitespace or pipes. Use `re.findall` over the relevant
   row, then pick the column matching the question's units (millions vs
   thousands).

4. **Cross-validate when multiple sources** — if two source files give
   different numbers for the same quantity, prefer the one closer to the
   question's date / scope. Treasury bulletins sometimes report
   restatements years later.

5. **Convert units to the answer's expected form**. The grader does
   numerical match — `72.422` billion and `72422000000` are both correct
   if the question's expected answer is the integer dollar amount.
   Default to the most-precise numeric form unless the question implies
   otherwise.

## Output format

- **Numbers**: digits only.
  - Right: `72422000000`, `12345.67`, `0.0234`
  - Wrong: `$72,422,000,000`, `72.42 billion`, `seventy-two billion`
- **Dates**: ISO form `1942-12-31` or year `1942` matching the question's
  granularity.
- **Phrases**: short, no quotes, no leading articles.

## Common Pitfalls

- **Wrong units**: question asks "in millions", you wrote the raw value.
  Read the question precisely.
- **Currency vs count**: the answer might be a count of accounts, not a
  dollar amount. Scan the question for `how much / how many / what
  total` distinctions.
- **Off-by-year**: Treasury fiscal years span Oct-Sep until 1976, then
  shifted. Date in question may not map to the same calendar year in
  the source.
- **Multi-table aggregation**: some questions require summing across
  rows or sub-totals. Verify by computing the sum, not by trusting a
  single cell.
- **Don't paraphrase**: if the question expects a number, do NOT write
  a sentence. The grader takes the first non-empty line as the answer.
- **Don't include reasoning**: only the final answer goes to output.txt.
