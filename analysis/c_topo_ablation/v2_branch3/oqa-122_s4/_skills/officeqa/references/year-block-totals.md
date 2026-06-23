# Anchor multi-year totals to the requested year block

Use this chapter when a parsed financial table contains adjacent annual blocks
that repeat subtotal labels such as `Total`, `Annual total`, or similar rows.

```python
def extract_year_block_total(blocks, target_year):
    block = next((b for b in blocks if b.get("year") == target_year), None)
    if block is None:
        raise ValueError("requested year block not found")
    total_row = next((r for r in block["rows"] if r.get("label") == "Total"), None)
    if total_row is None:
        raise ValueError("no total row inside requested year block")
    return parse_numeric(total_row["value"])
```

## Procedure

1. Locate the parent annual block that matches the requested year or the file's
   intended year context before reading any subtotal.
2. Confirm that the candidate `Total` row still belongs to that parent block,
   not a neighboring earlier or later year section.
3. Treat stacked layouts with repeated subtotal labels as block-structured tables,
   not flat lists of rows.
4. If the OCR text is awkward, use nearby month rows, the block header, or file-year
   context to re-establish the chosen block boundary before extracting the subtotal.
5. Build the multi-year vector by repeating the same block-first extraction rule for
   every requested year.

## Runtime branches

- **If each annual block has an explicit year label near its subtotal**, bind the
  subtotal directly to that year and continue.
- **If the year label appears only at the start of a stacked block**, verify that the
  subtotal is still within that block by walking through the intervening rows before
  accepting it.
- **If a neighboring year's subtotal is more visually salient than the requested one**,
  treat that as a warning sign and re-check parent-block membership before computing.

```python
series = []
for year in requested_years:
    value = extract_year_block_total(blocks, year)
    series.append((year, value))
if len(series) != len(requested_years):
    raise ValueError("incomplete year-block series")
```

## Verification

Verify that every extracted subtotal is attached to the requested parent year block
and that no neighboring-year subtotal was substituted anywhere in the final series.
If any year cannot be tied back to its block label or block context, stop and rebuild
that year's extraction from the table structure before doing any downstream statistic.
If one extracted value appears to come from the next or previous annual block, discard
that partial series and re-anchor all requested years block-by-block rather than
patching a single suspicious number in place.
