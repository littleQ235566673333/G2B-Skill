---
name: searchqa
description: Use this skill whenever the user asks a Jeopardy-style or short-factoid question that comes with a bundle of pre-fetched search-result snippets. The task is to read the snippets, extract the single short answer the question implies, and write it to output.txt — one line, the literal answer string only.
---

# Snippet-grounded short-answer QA

The input is plain UTF-8 text at `input.txt`. It contains ~50 search-result
snippets concatenated end-to-end. Each snippet starts with the markers
`[DOC] [TLE] <title> [PAR]` followed by paragraph text. The answer to the
question is mentioned (often verbatim) in the snippets.

Output goes to `output.txt`: one line, the short answer string only — no
explanation, no units the question didn't ask for, no surrounding quotes.
Articles (`a/an/the`) and most punctuation are stripped in evaluator
normalization but cleaner output is preferred.

## Quick Start

```python
from pathlib import Path

text = Path("input.txt").read_text(encoding="utf-8")

# Pull out paragraph text only (strip the [DOC]/[TLE]/[PAR] markers)
import re
parts = re.split(r"\[DOC\]\s*\[TLE\][^\[]*\[PAR\]", text)
paragraphs = [p.strip() for p in parts if p.strip()]

# Concatenated context to scan; for short factoid Qs you can usually find
# the answer with a careful Python search rather than re-reading every doc.
ctx = " ".join(paragraphs)

# … your extraction logic here …
answer = "Rocky"

Path("output.txt").write_text(answer + "\n", encoding="utf-8")
```

## Reading the question carefully

The questions are Jeopardy-style: a clue describing the answer rather than
a direct question. Examples:

- `1976: "A Single Colorado Mountain"` → name a mountain (answer: "Rocky").
- `In 1959 he became the first person to play himself in a movie` → name a
  person.
- `This Greek letter is also a brainwave` → name a letter.

The answer is almost always a **named entity** (person / place / work /
proper noun) or a **short phrase**. Rarely a number or year.

## Strategy that works well

1. **Scan for the most-mentioned proper noun** in the snippets. Jeopardy
   clues are designed so the answer recurs across the gold corpus, so the
   highest-frequency capitalized phrase is usually it.
2. **Filter against question terms.** If the question contains a year /
   place / role, prefer entities that co-occur with those constraints
   inside the same snippet.
3. **Disambiguate via title fields** (`[TLE] ...`). Article titles in the
   snippets are strong cues — Wikipedia / encyclopedia titles are often the
   exact answer string.

A simple, robust pipeline:

```python
from collections import Counter
import re

text = Path("input.txt").read_text(encoding="utf-8")
# Capitalized multi-word phrases (rough proper-noun proxy)
candidates = re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", text)
freq = Counter(candidates)
# Drop generic short caps that are noise
generic = {"The", "A", "I", "He", "She", "It", "They", "This", "That"}
for g in generic:
    freq.pop(g, None)
# Top candidates
top = freq.most_common(10)
```

Often `top[0][0]` is the answer. If not, scan the top-5 against the
question's constraints (year, location, role).

## Common Pitfalls

- **Multi-word entities**: don't write only the first token. "Rocky
  Mountain", "Albert Einstein", "Star Wars" — emit the full phrase.
- **Capitalization-only candidates can over-match common words**. Always
  filter against a small generic-word stoplist before counting.
- **Answer may be a verb phrase or short common-noun phrase** for some
  Jeopardy categories ("A Letter" / "A Word"). Fall back to scanning the
  paragraph that most-densely overlaps the question's keywords.
- **Don't paraphrase**: if the snippets say "Rocky", write "Rocky", not
  "the Rocky Mountains" or "Rocky Mountain range".
- **Don't add the question category prefix**. The category name in the
  question is context, not part of the answer.
- **Single answer line**: write exactly one line. Multi-line output is
  scored as the first line only.
