---
name: officeqa
description: Answer grounded questions over parsed financial-document text by locating the right file, table, or series, extracting the exact value, normalizing units and dates, and writing one-line output.
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
question_keywords = ["year", "series"]
for name, txt in texts.items():
    for kw in question_keywords:
        for m in re.finditer(re.escape(kw), txt, flags=re.IGNORECASE):
            start = max(0, m.start() - 200)
            end   = min(len(txt), m.end() + 200)
            print(f"\n[{name}] @{m.start()}: ...{txt[start:end]}...")

# 4. Extract the value after checking scope, units, and date alignment
answer = "0"

# 5. Write the answer
Path("output.txt").write_text(answer + "\n", encoding="utf-8")
```

## Classify the evidence before choosing an operation

1. **Decide whether the question asks for** a direct cell lookup, a full
   dated series, an aggregation/regression over several values, a
   transformation that combines document values with another stated series,
   or a visual-property readout that needs plotted geometry rather than prose.
2. **Match the source structure to that need**: auction or issuance rows are
   event snapshots, while market-price tables are dated series; wide annual
   tables support regressions only after selecting the correct category; chart
   captions and axis labels are not themselves the plotted line or bar shapes.
3. **Use artifact contents before prompt wording** when choosing the branch.
   If the files show a dated series, treat later wording about a bond or issue
   as series-identification metadata rather than permission to collapse to one row.
4. **Check modality sufficiency before extracting figure answers**. If the task
   asks for peaks, crossings, slopes, bar counts, or other geometric properties,
   confirm the available artifact contains coordinates or the actual plotted shape;
   otherwise do not infer the count from captions, notes, or exhibit titles.

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

## Read tables and series by full scope

For security-specific or year-series questions, audit the available file/date
coverage before computing, then verify that the data you found covers the full
requested scope that is actually present. Match the full security or category
descriptor, prefer the direct summary table whose header semantics already match
the requested aggregate, and collect every dated observation or yearly total in range.
For growth or change between named calendar months, prefer the by-period monthly
series over cumulative-through-date snapshots unless the prompt explicitly asks for
a cutoff-date cumulative amount. For list outputs, inventory the requested years or
dates first and verify you have exactly one in-scope observation per requested period
before finalizing. In repeated monthly row layouts, choose one row category from the
prompt semantics, keep that same row label across every month and every joined table,
and reject mixes of nearby labels such as domestic/abroad/worldwide aggregates. For
security-event or volatility tasks, restate the grouping key first, inventory all
candidate observations in the supplied artifact, drop out-of-window rows, and verify
that no in-range reopening or related matching event is missing before computing. In
hierarchical tables, lock the exact requested category level before extraction: when
the prompt names a subcategory or subtotal, use that row consistently across periods
rather than a broader table total. For Treasury bulletin tasks with several nearby debt
or ownership table families, verify table title and row label together against the full
prompt semantics before extraction: survey snapshot vs debt-outstanding family, exact
debt subclass, and requested total/subtotal scope must all match at once. When a
question names an ownership survey snapshot and a debt subclass, reject nearby
maturity-distribution, general debt-outstanding, or broader marketable-securities
tables that share keywords but not the full requested semantics. For pairwise
statistics taken from one row, lock each operand definition from the header and any
footnote in words before copying numbers, and reject adjacent columns whose labels only
partially match the prompt's wording. For event-based period averages, scan the whole
period report and include every in-scope occurrence even when headings vary or combine
multiple instruments in one title.

```python
available = audit_available_coverage(source_files)
series = select_semantic_match(candidate_tables, target_descriptor)
values = [parse_value(r) for r in series if in_available_requested_range(r, available)]
if not values:
    raise ValueError("no in-scope observations found")
result = summarize(values)
```

Decision rule: if the requested span is not present in the supplied files, do not
fabricate missing years or rebuild the answer from narrower partial tables when a
direct matching summary table already exists.
Read references/series-scope-reconstruction.md when the task requires reconstructing
an exact security/event series, locking one repeated row label across joined monthly
tables, selecting an exact requested subtotal instead of a broader total, proving
completeness before a statistic, or distinguishing a by-period monthly series from a
cumulative-through-date snapshot. Skip when the answer is a single direct lookup from
one already-unambiguous row or cell.

## Reconstruct wide repeated-column tables before aggregation

When a historical table repeats the same value-group headings across the page,
stop before averaging or comparing. Count repeated column groups and row blocks,
audit how dates are distributed across them, and build an explicit keyed map
before any aggregation. Do not infer year order from row order alone, and do not
average from OCR slices whose year/group headers are missing unless surrounding
page structure lets you prove the mapping.

```python
cell_map = {}
for block in row_blocks:
    for row in block:
        month = parse_month(row)
        for group in repeated_groups:
            year = infer_year(block, group)
            cell_map[(year, month)] = extract_group_values(row, group)
if not cell_map:
    raise ValueError("layout not reconstructed")
```

Decision rule: if the same headings repeat horizontally and the requested years
span more than one visual block, do not aggregate directly from visible columns.
Read references/wide-table-layout.md when the table repeats the same value triplet
or measure-group across multiple horizontal blocks. Skip when each date/year already
appears once in a simple vertical series.

## Normalize units before modeling or aggregation

Read the table title/header for units, convert extracted values into the question's
requested unit immediately, and audit the final output scale separately before
writing digits-only output. For regression, forecasting, averaging, or other modeling
over a historical vector, convert every observation into the requested unit before
fitting or aggregating; do not fit in table-reported millions or thousands and only
rescale the final prediction afterward. For percent change or percent difference questions,
subtraction is only an intermediate step: restate the named formula first, then use
the correct denominator and multiply by 100. `Percent change` uses the stated
baseline direction; `absolute percent difference` uses the average of the compared
values as the baseline. For named statistics over a derived series, restate the
requested quantity as a formula before finalizing so intermediate results such as
a standard deviation are not emitted when the prompt asks for a normalized statistic
such as coefficient of variation. When the prompt asks for extraction-only output such
as a dated list or table-native series, preserve the reported table scale unless the
prompt explicitly asks for rescaling. When several textbook conventions exist for a
named coefficient, restate the exact formula on the extracted vector and compute the
denominator explicitly before rounding. For two-value Gini tasks, write the intended
formula before arithmetic, keep it as a coefficient unless the prompt asks for percent,
and reject half-scale results that signal a denominator mismatch. For digits-only numeric answers, decide at the
end whether the output should stay in reported units or be expanded to evaluator base
units such as raw dollars, then perform that conversion immediately before writing.
Finish with a magnitude sanity check: compare the computed result to the requested
unit/statistic label so a billions answer is not still at millions scale, a named
normalized statistic is not still an intermediate dispersion or gap measure, and a
two-value coefficient is not obviously off by a factor implied by the wrong convention.

```python
import numpy as np

values = np.array(extracted_values, dtype=float)
scaled = values * unit_scale
result = compute_quantity(scaled)
final_answer = convert_to_output_units(result, output_scale)
```

Decision rule: if your computed value is still in dollars, millions, or another
source unit while the question asks for a percent, coefficient of variation, Gini coefficient,
or other named normalized statistic, re-open the denominator or final formula choice before
changing the extraction.

## Align dates across joined series

When combining a Treasury series with FX, index ratios, or another dated input,
assign each observation the rate for the same stated date/year before forecasting
or comparing outputs.

```python
aligned = []
for obs in observations:
    rate = lookup_rate(obs["date"], rate_series)
    aligned.append(convert(obs["value"], rate))
answer = summarize(aligned)
```

Decision rule: if the task mixes values from several years, audit every converted
observation with the question "which exact year/date rate did I use for this one?"

## Anchor multi-year totals to the requested year block

In stacked or adjacent year sections with repeated row labels such as `Total`,
locate the requested year block first, then read only that block's subtotal or
annual total. Treat OCR-awkward layouts as unresolved until the chosen total row
has been tied back to its parent year label or file-year context.

```python
year_block = find_year_block(table_text, target_year)
subtotal_row = find_block_row(year_block, "Total")
if subtotal_row is None:
    raise ValueError("missing total in requested year block")
value = parse_total(subtotal_row)
```

Decision rule: if a neighboring year block is visually closer or more salient than
the requested one, treat that as a cue to re-check block boundaries before extracting.
Read references/year-block-totals.md when a multi-year table repeats `Total` or subtotal
rows across adjacent annual blocks. Skip when the requested value comes from a single
one-year table with no repeated subtotal labels.

## Build complete within-period event sets before period averages

For quarterly or yearly averages over auctions or financing events, scan the full
period report and enumerate every in-scope event before averaging, fitting, or
forecasting. Treat varying or combined headings as possible containers for the same
target event family rather than evidence that later matches are out of scope.

```python
matches = []
for section in period_sections:
    if is_target_event(section, target_security):
        matches.append(extract_event_value(section))
if not matches:
    raise ValueError("no in-period events found")
period_average = sum(matches) / len(matches)
```

Decision rule: if a report covers multiple months and you found only one matching
event, treat the period as incomplete until you verify the remaining months.

## Derive the metric input series before risk statistics

For expected shortfall, VaR, or similar named risk measures, determine whether the
metric is defined on reported levels, simple returns, log returns, price returns,
yield changes, spreads, or losses, then write that helper-series definition before
taking tails or quantiles. Preserve the prompt's sign convention after the tail statistic
is computed rather than flipping a negative loss into a positive magnitude by default,
and keep the requested percent units explicit. Do not default to year-over-year percent
change on quoted levels just because the table is dated; choose the metric domain that
the financial convention in the prompt actually names.

```python
derived = [transform_pair(prev, cur) for prev, cur in zip(levels, levels[1:])]
if not derived:
    raise ValueError("no derived observations for risk metric")
threshold = tail_cutoff(derived, confidence)
answer = summarize_tail(derived, threshold)
```

Decision rule: if the prompt names a historical return or portfolio-loss approach but
your candidate answer is still one of the raw observed levels, or comes from an unstated
default return convention, stop and derive the metric input series first.
Read references/risk-series-conventions.md when a task asks for expected shortfall, VaR,
or another tail/risk metric whose helper return/loss series and sign convention are not
obvious from the raw table values. Skip when the prompt directly asks for a simple change,
level lookup, or other non-risk statistic on an already-defined series.

## Separate document facts from external operands

Some questions require both values found in the source files and another explicitly
requested series or price basis. Label each operand by provenance before combining,
then verify the exact requested measure for any non-document operand: level vs index,
annual average vs point-in-time, frequency, adjustment status, historical vintage or
rebasing, and directional convention such as base-per-quote versus quote-per-base. For
outside price series, pin down nominal vs real, per-unit level vs rebased index, and
unit basis before multiplying, then reject candidates whose scale is incompatible with
the requested convention or would collapse back to a statutory/accounting basis instead
of the requested market or real-price operand. For outside exchange-rate operands, do
not use a nearby document-side country row, index-like series, or other exchange-like
number unless year/date, annual-averaging or point timing, nominal/real status, and
currency direction all match exactly. For CPI conversions, first pin the exact CPI
variant, seasonal-adjustment status, month values, and one consistent historical scale,
then convert document-side nominal values with `CPI_target / CPI_source` before any
later percent statistic; rebased modern CPI presentations or nearby month values are not
harmless substitutes for the requested monthly operand.

```python
inputs = {
    "document_values": extract_document_values(texts),
    "external_series": get_required_series(),
}
if inputs["external_series"] is None:
    raise ValueError("missing required non-document operand")
answer = combine(inputs["document_values"], inputs["external_series"])
```

Decision rule: if a candidate operand is semantically nearby but would make the
calculation use an index as a rate, use the wrong rebasing or seasonal-adjustment
variant, reverse the requested direction, or produce an implausible magnitude for the
stated convention, reject it before computing.
Read references/external-operands.md when the task combines document values with an
exchange rate, market price, real-price series, CPI-based constant-dollar conversion,
or another operand whose provenance is not already explicit in the source files. Skip
when every operand is directly stated in one in-document table and no outside series
selection is needed.

## Output format

- **Numbers**: digits only.
  - Right: `72422000000`, `12345.67`, `0.0234`
  - Wrong: `$72,422,000,000`, `72.42 billion`, `seventy-two billion`
- **Dates**: ISO form `1942-12-31` or year `1942` matching the question's
  granularity.
- **Phrases**: short, no quotes, no leading articles.

## Common Pitfalls

- **Wrong units or statistic**: table headers often state units once for the whole layout.
  Normalize to the question's requested unit before regression, aggregation, comparison,
  or final readout, then confirm the final digits-only answer is at the intended scale and
  represents the named statistic rather than an intermediate gap or dispersion measure. If
  the task asks for a list or direct extraction, preserve reported table units unless the
  prompt requests conversion, and if multiple normalization conventions are plausible,
  restate the exact denominator on the extracted vector before rounding. Distinguish
  percent change from absolute percent difference before arithmetic starts, and for
  digits-only channels decide explicitly whether the final scalar should remain in reported
  millions/billions or be expanded to evaluator base units such as raw dollars.
- **Wrong scope**: using a coupon match, one auction row, one subtotal, one
  repeated-column slice, an unavailable date span, a cumulative snapshot when the task
  asks for a by-period monthly series, mixed row labels from repeated monthly scopes, an
  incomplete security/event set when the task requires one locked grouping key and the
  full in-scope observation inventory, a broader table total when the prompt names a
  narrower requested subtotal such as a marketable category, a semantically nearby
  Treasury table family whose title/row words overlap without matching the exact survey,
  debt subclass, and requested total scope, or an adjacent column whose header/footnote
  semantics do not exactly match the requested operand definition.
- **Date misalignment**: when joining series across years, a nearby year's rate can
  look plausible but still be wrong. Audit every observation-to-rate mapping.
- **Wrong metric domain**: named risk statistics usually apply to a derived return,
  spread, yield-change, price-return, or loss series rather than raw reported levels.
  Build the metric input series, verify its observation count, state the sign convention,
  and do not default to an unstated return definition before taking tails or quantiles.
- **Missing operand provenance**: do not invent CPI, spot, or exchange-rate inputs,
  and do not treat an index, wrong vintage, wrong adjustment variant, statutory valuation basis,
  semantically nearby table, or document-side exchange-like value as the requested market operand
  without checking measure type, year, frequency, nominal/real status, scale, direction, and
  whether the selected outside price or FX series is the exact requested level rather than a
  rebased index or fallback accounting basis.
- **Modality mismatch**: chart questions about peaks, crossings, bars, or slopes need
  plotted geometry or explicit coordinates. Do not infer visual counts from captions, notes,
  or OCR text that omits the figure trace itself.
- **Currency vs count**: the answer might be a count of accounts, not a
  dollar amount. Scan the question for `how much / how many / what
  total` distinctions.
- **Off-by-year**: Treasury fiscal years span Oct-Sep until 1976, then
  shifted. Date in question may not map to the same calendar year in
  the source.
- **Don't paraphrase**: if the question expects a number, do NOT write
  a sentence. The grader takes the first non-empty line as the answer.
- **Don't include reasoning**: only the final answer goes to output.txt.
