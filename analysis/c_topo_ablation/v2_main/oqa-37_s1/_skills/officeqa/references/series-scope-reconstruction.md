# Reconstruct exact series scope before statistics

Use this chapter when a task requires building a statistic from a security-specific
series, a repeated monthly row layout, or an event set whose membership is not already
obvious from one row.

```python
def collect_in_scope(candidates, key_fn, in_window, scope_label=None):
    chosen = []
    for row in candidates:
        if scope_label is not None and row.get("scope") != scope_label:
            continue
        if not in_window(row):
            continue
        if key_fn(row) is None:
            continue
        chosen.append(row)
    if not chosen:
        raise ValueError("no in-scope observations after scope lock")
    return chosen
```

## Procedure

1. Restate the grouping key before extracting values: exact issue vs family,
   one row label vs another repeated scope row, one subtotal vs a broader total,
   one by-period monthly series vs a cumulative snapshot, or one operand definition
   vs an adjacent column with similar wording.
2. Inventory all candidate observations visible in the supplied artifact before
   computing any statistic.
3. Lock one scope label or grouping rule and apply it consistently across every
   month, joined table, event section, or operand pair.
4. Drop out-of-window observations and reject rows or columns that match topic
   words but not the locked scope.
5. Verify completeness: check that no in-range reopening, repeated monthly row,
   same-definition event, requested subtotal, or header-defined operand was skipped.

## Runtime branches

- **If the task is about a repeated monthly table with labels such as office or region
  scope**, choose the single row label implied by the question and reuse exactly that
  label across every month and every joined series.
- **If the task is about a security or instrument series**, decide whether identity is
  exact issue or broader family before collecting values, then include every in-range
  matching observation exactly once.
- **If the task is about event-based averaging or volatility from narrative sections**,
  scan the full period for repeated occurrences and treat a one-row match as incomplete
  until the remaining sections have been checked.
- **If the task asks for change or growth between named calendar months**, prefer the
  direct by-period monthly series for those named months and reject cumulative-through-date
  summaries unless the prompt explicitly asks for a cutoff-date cumulative amount.
- **If the task asks for a Treasury ownership-survey snapshot or another narrowly named
  debt subclass**, verify that the chosen row contains every qualifier from the prompt
  such as survey date, total/subtotal scope, marketable/public/publicly held class, and
  interest-bearing status; reject broader marketable totals unless every qualifier matches.
- **If the task computes a pairwise statistic from one table row**, restate both operands
  in words from the header and any footnotes before copying numbers, and reject adjacent
  columns whose labels are only partially aligned with the prompt wording.

```python
observations = collect_in_scope(candidates, grouping_key, in_window, scope_label)
keys = [grouping_key(row) for row in observations]
if len(keys) != len(set(keys)):
    raise ValueError("duplicate keyed observations in final series")
result = compute_statistic(observations)
```

## Verification

Verify three things before finalizing: every observation satisfies the locked grouping
rule, every observation lies inside the requested date window, and the final set is
complete for the artifact actually supplied. If a same-scope month, reopening, event,
requested subtotal, or operand definition is missing, return to the candidate inventory
step and rebuild the observation list before any further computation. If mixed row labels
or semantically broader fallback totals appear in the final vector, discard the vector,
restate the scope label once, and recollect the series from scratch.
