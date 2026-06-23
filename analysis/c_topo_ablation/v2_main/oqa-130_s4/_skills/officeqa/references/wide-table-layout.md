# Reconstruct wide repeated-column tables before aggregation

Use this chapter when a parsed Treasury or financial table repeats the same
measure headings across multiple horizontal groups and the requested years or
months are distributed across those groups.

```python
from collections import defaultdict

cell_map = {}
for block_index, block in enumerate(row_blocks):
    for row in block:
        month = parse_month(row)
        for group_index, group in enumerate(repeated_groups):
            year = infer_year_from_headers(block_index, group_index, headers)
            values = extract_group_values(row, group)
            if year is not None and month is not None and values is not None:
                cell_map[(year, month)] = values

if not cell_map:
    raise ValueError("failed to reconstruct any dated cells")
```

## Procedure

1. Count the repeated horizontal value groups before reading any numbers.
2. Count the vertical row blocks and identify whether months repeat inside each block.
3. Infer the year assignment for each `(block, group)` pair from nearby headers,
   captions, or explicit year labels.
4. Audit at least three concrete cells across the requested span: one early,
   one middle, and one late.
5. Build an explicit `(year, month) -> values` map and aggregate only from keys
   proven to be in scope.

## Runtime branches

- **If year labels are explicit for every group**, map groups directly from the labels
  and continue to the audit step.
- **If year labels are only partial or appear once per block**, infer tentative group-year
  assignments, then verify them against multiple labeled month rows before aggregating.
- **If OCR/text extraction drops the year/group labels needed to justify the mapping**, stop
  and treat the layout as unresolved rather than assuming years advance sequentially down the
  visible row order.

```python
sample_keys = [min(cell_map), sorted(cell_map)[len(cell_map)//2], max(cell_map)]
for key in sample_keys:
    print(key, cell_map[key])

requested = {
    key: values
    for key, values in cell_map.items()
    if start_year <= key[0] <= end_year
}
if not requested:
    raise ValueError("requested date range not present after layout reconstruction")
```

## Verification

Verify that the reconstructed map contains the expected months for each requested year
and that audited early/middle/late keys match the visible table labels. If any audited
key disagrees with the table text, stop and redo the year-group inference before
computing spreads or averages. If months are missing for an in-scope year, return to the
block/group mapping step and resolve the missing section instead of averaging partial data.
If you cannot prove the year/group mapping from surviving headers or surrounding page
structure, halt and seek a better-preserved source slice before any further aggregation.
