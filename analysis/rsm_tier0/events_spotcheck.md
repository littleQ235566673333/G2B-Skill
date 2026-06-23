# RSM Tier 0 — spot-check sheet

**Total events**: 16
**Stratum A** (anti-wipe engaged, intercepted): 8
**Stratum B** (no anti-wipe, silent wipe): 8

Per-event verdict goes in the YAML field `my_verdict` of `events_filled.yaml`. Categories per template.md:
- `destructive` — deleted content was useful
- `stale_cleanup` — deleted content was redundant / stale; anti-wipe was over-protective
- `ambiguous` — value unclear; default when in doubt

---

## Stratum A (8 events)

### [A1] g2b-v8_gpt-4.1_oqa-gpt41-smoke iter 3

- **anti_wipe_engaged**: yes
- **size change**: 122 → 122 lines (+0.0%)
- **patcher tried to write**: 700 B (vs pre 5697 B)
- **wipe_attempted / wipe_survived**: True / False
- **prev / next pre_correct**: 0 → 0 (Δ = 0)
- **next_iter_batch**: ['oqa-36', 'oqa-64', 'oqa-114', 'oqa-38']

**Patcher's self-summary excerpt** (would-be deleted/replaced):

```
# Patch Summary

**What changed:**

1. **New operation section in L2:**  
   - Added an H2 "Compute Gini coefficient for fund cash flows" with mechanistic instructions for which numbers (receipts/expenditures, exclude investments/assets) to extract and how to compute the Gini and surplus/deficit status.
   - Provided a generic example code and explicit format.
   - Pointer to a new L3 worked example (`references/gini_coefficient.md`) for concrete extraction/validation and correction steps.

2. **New L3 worked example:**  
   - `references/gini_coefficient.md` includes a table, step-by-step extraction, a runnable code block with runtime branch (label/row validation and bounds checking), and explicit corrective actions on verification failure.

3. **Common Pitfalls update:**  
   - Merged an
```
**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [A2] g2b-v8_gpt-4.1_ss-gpt41-fix iter 3

- **anti_wipe_engaged**: yes
- **size change**: 169 → 169 lines (+0.0%)
- **patcher tried to write**: 1120 B (vs pre 7195 B)
- **wipe_attempted / wipe_survived**: True / False
- **prev / next pre_correct**: 0 → 0 (Δ = 0)
- **next_iter_batch**: ['48257', '398-14', '147-48', '49667']

**Patcher's self-summary excerpt** (would-be deleted/replaced):

```
# Patch Summary (iter 3)

The following incremental structural improvements were applied to the skill, addressing robust header mapping, explicit group-to-row output mapping, per-row windowed aggregation, and literal answer mapping—directly guided by failures and contrastive group evidence from this iteration's rollouts:

---

## 1. Robust Header Mapping (L2 + L3)

- **New L2 pointer**: Added a "Explicit Header Mapping for Lookups" section, instructing to scan/match/map by the actual sheet header values, normalizing as needed.
- **New L3 reference**: `references/header_mapping.md` explains detection, normalization, and verification for mapping required columns, with openpyxl/pandas code. This reference is now linked at the relevant operation point.
- **Pitfall updated**: "Not scanning and 
```
**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [A3] g2b-v8_gpt-4.1_ss-gpt41-fix iter 8

- **anti_wipe_engaged**: yes
- **size change**: 405 → 405 lines (+0.0%)
- **patcher tried to write**: 1724 B (vs pre 18591 B)
- **wipe_attempted / wipe_survived**: True / False
- **prev / next pre_correct**: 0 → 0 (Δ = 0)
- **next_iter_batch**: ['39432', '44389', '374-31', '91-34']

**Patcher's self-summary excerpt** (would-be deleted/replaced):

```
**Skill evolution complete (iteration 8):**

Based on the batch evidence and patterns:

---

**1. Multi-row header lookup (Pattern 1):**
- Added new H2: **Column Lookup with Multi-row Headers** — covers how to use both/all header rows to resolve columns, with Excel and Python examples, and L3 pointer to header mapping reference.

**2. Formula output vs literal value (Pattern 2):**
- Strengthened the "Output Format: Bare Value, Correct Cell, Explicit Mapping, and Required Order" section to warn: always compute and write numeric values directly unless Excel will handle formula recalculation—includes a verification step and explanation.

**3. Dynamic header-driven lookup, not positional (Pattern 3):**
- Enhanced the "Normalize and Map Headers Before Data Operations" section: always scan/norma
```
**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [A4] g2b-v8_gpt-4.1_ss-gpt41-fix iter 9

- **anti_wipe_engaged**: yes
- **size change**: 405 → 405 lines (+0.0%)
- **patcher tried to write**: 2052 B (vs pre 18591 B)
- **wipe_attempted / wipe_survived**: True / False
- **prev / next pre_correct**: 0 → 0 (Δ = 0)
- **next_iter_batch**: ['50916', '58147', '387-16', '53117']

**Patcher's self-summary excerpt** (would-be deleted/replaced):

```
The following incremental edits were made based on convergent evidence from overlapping failures and successes in diagnosing batch, overlay, and rollout logs. No wholesale rewrites were performed; only declarative, minimal edits and L3 lifts/expansions were applied at structurally targeted anchors.

---

## 1. Header Mapping, Normalization, Robust Block Pairing (Pattern: `dynamic-header-mapping-and-robust-pairing`)
- **SKILL.md’s “Normalize and Map Headers Before Data Operations” section:**
  - Strengthened requirements to (a) dynamically pair up related/compound columns (e.g., PO-x/cost) exclusively by normalized names, (b) handle all spelling variants/typos, and (c) surface explicit errors or prompt for user input if ANY required header or block pairing is missing after scanning/normaliz
```
**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [A5] g2b-v8_gpt-4.1_wtq-gpt41-fix iter 2

- **anti_wipe_engaged**: yes
- **size change**: 103 → 103 lines (+0.0%)
- **patcher tried to write**: 2167 B (vs pre 5005 B)
- **wipe_attempted / wipe_survived**: True / False
- **prev / next pre_correct**: 2 → 1 (Δ = -1)
- **next_iter_batch**: ['nt-197', 'nt-74', 'nt-260', 'nt-183']

**Patcher's self-summary excerpt** (would-be deleted/replaced):

```
Incremental patch summary (already written):

## Key new content and changes

1. **Schema inspection and value mapping (workflow/operation expansion):**
    - Added a new section to SKILL.md advising to scan the table schema when the target column is missing, and map available columns accordingly (e.g., using a list of known cities if searching for a country that isn’t present as a column).
    - This addresses contrastive evidence from nt-240, where direct column guesswork failed absent schema inspection.

2. **Disambiguate “next” in question language:**
    - Added a checklist to SKILL.md clarifying that “next to X” must be interpreted carefully — as adjacency or ranking based on context/wording.
    - Specifies both adjacency and ranking checks, handling ambiguous phrasing robustly and 
```
**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [A6] g2b-v8_gpt-4.1_wtq-gpt41-fix iter 5

- **anti_wipe_engaged**: yes
- **size change**: 185 → 185 lines (+0.0%)
- **patcher tried to write**: 2929 B (vs pre 10051 B)
- **wipe_attempted / wipe_survived**: True / False
- **prev / next pre_correct**: 0 → 0 (Δ = 0)
- **next_iter_batch**: ['nt-53', 'nt-325', 'nt-323', 'nt-178']

**Patcher's self-summary excerpt** (would-be deleted/replaced):

```
### Summary of Patch

1. **New H2 added:** "Parsing and extracting values from score columns" — covering robust, generalizable methods for extracting and using per-team values from delimited score strings (critical for nt-19, nt-250).
2. **"Counting entities vs summing cell values" expanded:** Now includes how to count entity appearances across multiple participant columns (nt-141).
3. **"Extracting years from text columns" extended:** Covers extracting date for use in conditional aggregation (e.g., wins in year, nt-49).
4. **Common Pitfalls updated:** Merged new pitfalls (score strings, multi-column counting) with existing, avoiding duplicate or overly specific items.

All edits are incremental and compliant with the structural and YAGNI principles: no unnecessary new sections, no drift i
```
**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [A7] g2b-v8_gpt-4.1_wtq-gpt41-fix iter 6

- **anti_wipe_engaged**: yes
- **size change**: 185 → 185 lines (+0.0%)
- **patcher tried to write**: 1264 B (vs pre 10051 B)
- **wipe_attempted / wipe_survived**: True / False
- **prev / next pre_correct**: 0 → 0 (Δ = 0)
- **next_iter_batch**: ['nt-72', 'nt-165', 'nt-316', 'nt-18']

**Patcher's self-summary excerpt** (would-be deleted/replaced):

```
Skill evolution complete.  
Summary of incremental changes:

### In SKILL.md

- **Counting entities vs summing cell values:**  
  Expanded instructions to explicitly warn against summing unless a dedicated, validated count column exists. Added an L3 pointer:  
    `Read references/count_vs_sum.md when a candidate per-row count column is ambiguous, or when unsure if a numeric column encodes true entity counts.`

- **Flexible entity matching from descriptive columns:**  
  New H2 section.  
  - Covers compositional substring (AND/OR mask) logic for entity extraction in text blobs.  
  - Python and Excel generic code.
  - L3 pointer:  
    `Read references/entity_matching_multi_aspect.md when more than two attributes or ambiguous phrasing are present.`
    
- **Extracting entities from multi-
```
**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [A8] g2b-v8_gpt-4.1_wtq-gpt41-fix iter 9

- **anti_wipe_engaged**: yes
- **size change**: 242 → 242 lines (+0.0%)
- **patcher tried to write**: 3428 B (vs pre 14593 B)
- **wipe_attempted / wipe_survived**: True / False
- **prev / next pre_correct**: 2 → 1 (Δ = -1)
- **next_iter_batch**: ['nt-41', 'nt-229', 'nt-378', 'nt-46']

**Patcher's self-summary excerpt** (would-be deleted/replaced):

```
Incremental evolution applied:

**1. Added new L2 operation H2: "Previous/next entity lookup using rank columns":**
- Provides clear, general instructions and code for answering "Who is next/previous in rank?" via explicit numeric rank columns, not table row adjacency. Includes a decision rule on when to use rank vs. row order.

**2. Added new L2 operation H2: "Selecting the entity associated with max/best/worst score or value":**
- Guides how to reliably return the appropriate entity (person, team, etc.) for "who" questions querying for max/best, rather than emitting summary, record, or outcome columns. Gives small generic code and an explicit decision rule.

**3. Strengthened Common Pitfalls:**
- Incorporated precise bullets to match the above operations, focusing on:
  - Not using row a
```
**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

## Stratum B (8 events)

### [B1] g2b-skill-spreadsheet_gpt-4.1_v6 iter 4

- **anti_wipe_engaged**: no
- **size change**: 40 → 2 lines (-73.9%)
- **patcher tried to write**: -1 B (vs pre 1682 B)
- **wipe_attempted / wipe_survived**: False / True
- **prev / next pre_correct**: None → None (Δ = None)
- **next_iter_batch**: ['54274', '47766', '50521', '45707']

**Top-3 deleted rule lines** (line-level diff snap_N → snap_(N+1)):

1. (unknown) Apply this logic when the task involves N-way matching between worksheet regions by keys, and the output must reflect presence/absence in the reference.
2. (unknown) - **`ws.max_row` overcounts**: May include formatted-but-empty rows. Scan the column to find the last non-empty cell when you need the true data range.
3. (unknown) Use a multicolumn "join" logic to check if a row in a target worksheet region matches any row in a reference region across multiple key fields.

**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [B2] g2b-skill-wtq_gpt-4.1_v6 iter 6

- **anti_wipe_engaged**: no
- **size change**: 138 → 1 lines (-96.7%)
- **patcher tried to write**: -1 B (vs pre 6040 B)
- **wipe_attempted / wipe_survived**: False / True
- **prev / next pre_correct**: None → None (Δ = None)
- **next_iter_batch**: ['nt-72', 'nt-165', 'nt-316', 'nt-18']

**Top-3 deleted rule lines** (line-level diff snap_N → snap_(N+1)):

1. (unknown) When asked for the entity with the highest value in a column (e.g., "Which material has the highest conductivity?"), scan for the maximum and emit only the associated entry. Unless there are ties, return a unique row:
2. (unknown) - Some questions ask for **one** answer (e.g., "what was the last year ..."), others ask for **a set** (e.g., "which countries ..."). Read carefully — emitting one answer for a set-question, or vice versa, will fail.
3. (unknown) - For any question with two or more constraints mappable to columns, filter using all of them (binary, categorical, and numeric) combined with logical AND, prior to answer selection or aggregation.

**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [B3] g2b-v8_gpt-4.1_ss-gpt41 iter 7

- **anti_wipe_engaged**: no
- **size change**: 177 → 9 lines (-92.4%)
- **patcher tried to write**: 3367 B (vs pre 13254 B)
- **wipe_attempted / wipe_survived**: True / True
- **prev / next pre_correct**: 0 → 0 (Δ = 0)
- **next_iter_batch**: ['32789', '44017', '55427', '382-10']

**Top-3 deleted rule lines** (line-level diff snap_N → snap_(N+1)):

1. (introduced_in_iter_3) - **Enumerate actual sheet headers and their row indices before referencing any columns. Map task-language column names to sheet headers, scan downward to locate headers when not at row 1, reconcile any mismatches, and explicitly log mapped
2. (introduced_in_iter_3) Read references/aggregation_preserve_fields.md for ambiguous cases, strict output formatting, or handling meta column preservation. Read references/numeric_coercion_before_arithmetic.md when input may contain blanks, errors, or non-numeric 
3. (introduced_in_iter_5) When a fill/aggregation should occur only when a condition involving the next row (e.g., next date's day=1) holds, output must be written in the current (trigger) row—not offset. For each row, check the next row for condition, then aggregat

**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [B4] g2b-v8_gpt-4.1_wtq-gpt41 iter 4

- **anti_wipe_engaged**: no
- **size change**: 123 → 24 lines (-63.4%)
- **patcher tried to write**: 2623 B (vs pre 7176 B)
- **wipe_attempted / wipe_survived**: True / True
- **prev / next pre_correct**: 1 → 1 (Δ = 0)
- **next_iter_batch**: ['nt-19', 'nt-49', 'nt-141', 'nt-250']

**Top-3 deleted rule lines** (line-level diff snap_N → snap_(N+1)):

1. (introduced_in_iter_1) Some questions require checking for a value or attribute across multiple columns of a row (e.g., "did the item ever meet criterion X", or "does the row have both attributes Y and Z"). For these, scan *all relevant columns* for each row and 
2. (introduced_in_iter_2) Don’t match only by substring/literal; consider synonyms and table context (e.g., "Date", "Year", "Founded"). Check all headers and select by meaning—use substring matches, synonyms, and typical column roles when header is ambiguous. Always
3. (introduced_in_iter_3) When counting or aggregating entities (names, teams, etc.), treat each cell in the column as a single atomic entity, even if it contains multiple tokens (e.g., full name). Do not split by spaces unless the cell contains an explicit list (e.

**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [B5] g2b-v8_gpt-4.1_wtq-gpt41 iter 8

- **anti_wipe_engaged**: no
- **size change**: 129 → 8 lines (-88.5%)
- **patcher tried to write**: 772 B (vs pre 6766 B)
- **wipe_attempted / wipe_survived**: True / True
- **prev / next pre_correct**: 0 → 0 (Δ = 0)
- **next_iter_batch**: ['nt-345', 'nt-123', 'nt-343', 'nt-47']

**Top-3 deleted rule lines** (line-level diff snap_N → snap_(N+1)):

1. (unknown) When no single "count/total" column exists, answer may require aggregation or search across related fields. For tasks requiring matching on multiple conditions (e.g., entity, role, institution), ensure all criteria are met in the same row b
2. (introduced_in_iter_7) When counting or extracting linked entries (e.g., Wikipedia-linked movies), check for both explicit string/link patterns (such as URLs or "[[...]]") and cell-level hyperlink metadata. Do not rely solely on text pattern matching—inspect cell
3. (introduced_in_iter_5) For numeric filtering (e.g., points > threshold), forcibly coerce to numeric using `pd.to_numeric(errors='coerce')`. Apply condition on all rows regardless of type-ambiguity. When ranking or finding extremes (max/min) for a substance (e.g.,

**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [B6] skillgrad_gpt-4.1_oqa-gpt41-smoke iter 1

- **anti_wipe_engaged**: no
- **size change**: 102 → 8 lines (-77.8%)
- **patcher tried to write**: 1034 B (vs pre 4245 B)
- **wipe_attempted / wipe_survived**: True / True
- **prev / next pre_correct**: 1 → 2 (Δ = 1)
- **next_iter_batch**: ['oqa-98', 'oqa-45', 'oqa-68', 'oqa-124']

**Top-3 deleted rule lines** (line-level diff snap_N → snap_(N+1)):

1. (unknown) description: Use this skill whenever the user asks a grounded reasoning question over U.S. Treasury Bulletin documents (or similar parsed-PDF financial corpora) and provides a directory of source text files. The task is to identify the rele
2. (unknown) - Numerical answers: digits only — no `$`, no commas, no `million/billion`
3. (unknown) The input is a `sources/` directory of plain UTF-8 text files parsed from

**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [B7] skillgrad_gpt-4.1_oqa-gpt41-smoke iter 5

- **anti_wipe_engaged**: no
- **size change**: 64 → 20 lines (-73.5%)
- **patcher tried to write**: 1096 B (vs pre 4142 B)
- **wipe_attempted / wipe_survived**: True / True
- **prev / next pre_correct**: 2 → 2 (Δ = 0)
- **next_iter_batch**: ['oqa-39', 'oqa-77', 'oqa-32', 'oqa-17']

**Top-3 deleted rule lines** (line-level diff snap_N → snap_(N+1)):

1. (introduced_in_iter_4) - **Multi-table aggregation, selection, or subset error**: Failing to match every relevant constraint (subset, type, timing, aggregation) or summing across subcomponents when not all constraints are satisfied leads to incorrect answers. Alw
2. (introduced_in_iter_3) Read references/table_extraction_validation.md when a table or row label does not exactly match all question constraints, or when aggregation must be constructed from subcomponents, or whenever any constraint/column match is ambiguous. Skip
3. (introduced_in_iter_4) - **Confirm precise match**: For each candidate table, row, or column, verify that all enumerated constraints are satisfied before selecting or aggregating any values. Consult table notes/footnotes for clarification if label matches are amb

**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---

### [B8] skillgrad_gpt-4.1_oqa-gpt41-smoke iter 7

- **anti_wipe_engaged**: no
- **size change**: 63 → 9 lines (-76.1%)
- **patcher tried to write**: 2160 B (vs pre 4961 B)
- **wipe_attempted / wipe_survived**: True / True
- **prev / next pre_correct**: 1 → 1 (Δ = 0)
- **next_iter_batch**: ['oqa-96', 'oqa-93', 'oqa-106', 'oqa-61']

**Top-3 deleted rule lines** (line-level diff snap_N → snap_(N+1)):

1. (introduced_in_iter_3) Always write the computed answer to the designated output cell or file as the last step. Then immediately read the output cell and confirm it is non-blank **and** matches the expected format (e.g., is numeric when a number is required, has 
2. (unknown) description: "Robust extraction, transformation, and computation in OfficeQA spreadsheet/document tasks, emphasizing output verification, constraint-driven extraction, correct unit/data transformation alignment, and reproducible results."
3. (introduced_in_iter_1)   Read references/table_extraction_validation.md when the table/row label does not match exactly or when the aggregated answer is not directly published. Skip when extraction is trivial and all constraints are obviously satisfied.

**Verdict**: _ambiguous_ (provisional)

**Notes**: _to fill_

---
