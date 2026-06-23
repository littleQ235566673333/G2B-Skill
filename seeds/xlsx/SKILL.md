---
name: xlsx
description: Use this skill whenever the user wants to do anything with Excel spreadsheet files (.xlsx, .xls, .csv). This includes reading data, writing formulas, manipulating cells, formatting, filtering, creating charts, pivot tables, and any spreadsheet automation tasks.
---

# Excel Spreadsheet Processing

Use `openpyxl` to read and write .xlsx files.

## Mandatory First Action

**Your VERY FIRST action on any spreadsheet task MUST be a shell call
that prints the input workbook's structure**. Do not skip this. Do
not "plan first then act" — print first, then plan from real data.

```python
python3 -c "import openpyxl; wb=openpyxl.load_workbook('INPUT_PATH'); \
print('sheets:', wb.sheetnames); \
[print(f'Row {i}:', r) for i, r in enumerate(wb[wb.sheetnames[0]].iter_rows(min_row=1, max_row=12, values_only=True), 1)]"
```

Replace `INPUT_PATH` with the actual input.xlsx path from the task. This
gives you the sheet names, header row, column letters, and first few
data rows — everything you need to map task descriptions to actual cell
locations. EVERY downstream decision (column letters, formulas, output
range) depends on this output.

If the task asks you to fix/translate/debug a VBA macro, the procedure
is the same: print structure first, then write Python (NOT VBA) that
performs the equivalent operation.

## Workflow: Verify Structure Before Operation

**Before any write, ALWAYS inspect the input workbook structure.** This
prevents the most common failure modes (wrong column, wrong sheet,
wrong row range) which collectively account for the majority of
spreadsheet-task errors.

Mandatory pre-flight steps:

1. List sheet names: `wb.sheetnames`
2. For the target sheet, print the first 5-10 rows including the header
   row, so you can see column letters AND header names.
3. Identify which column letter corresponds to each named field
   referenced in the task instruction (e.g., "model column" → which
   letter?). NEVER assume from task wording alone — check the printed
   structure.
4. Identify the data range: which rows contain real data vs blanks vs
   labels.

```python
from openpyxl import load_workbook

wb = load_workbook("input.xlsx")
print("Sheets:", wb.sheetnames)

ws = wb[wb.sheetnames[0]]
for i, row in enumerate(ws.iter_rows(min_row=1, max_row=10, values_only=True), 1):
    print(f"Row {i}:", row)
```

After printing, EXPLICITLY map task-described columns to letters before
writing any output.

## Quick Start

```python
from openpyxl import load_workbook

wb = load_workbook("input.xlsx")
ws = wb["Sheet1"]

value = ws["A1"].value
ws["B2"] = 42
ws["C2"] = "=SUM(A2:B2)"

wb.save("output.xlsx")
```

Use this for direct cell edits, formula updates, and simple workbook changes.

## Reading Data with pandas

```python
import pandas as pd

df = pd.read_excel('file.xlsx')                          # First sheet
all_sheets = pd.read_excel('file.xlsx', sheet_name=None) # All sheets as dict
```

## Writing Excel Formulas (vs computed values)

When the task asks for a "formula" or describes formula syntax, write
the formula STRING starting with `=`, not the computed value:

```python
ws["G4"] = "=SUMIF($C$4:$C$11, F4, $D$4:$D$11)"
```

When the task asks for a "calculation result" or "value", write the
numeric/string answer directly. If unclear, prefer formula form — it
preserves the intent and openpyxl will save it for Excel to evaluate.

## Output Verification

After writing, verify the output cell contents match what the task
described. For formula tasks, re-read the cell and check the string
starts with `=`. For value tasks, re-read and check the type/magnitude.

## Common Pitfalls

- **Cell indices are 1-based**: `ws.cell(row=1, column=1)` is A1.
- **`data_only=True` destroys formulas on save**: Use a separate workbook object for reading calculated values.
- **`ws.max_row` overcounts**: May include formatted-but-empty rows. Scan the column to find the last non-empty cell when you need the true data range.
- **Column letter vs header name confusion**: Tasks often describe a column by its header text. Always map header → column letter using the printed structure before writing. Wrong column is the #1 cause of silent failures.
