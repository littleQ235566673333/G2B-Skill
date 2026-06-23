import openpyxl
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_9/regression_gate/before_pass/core_9726/input.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb.active

rows = []
for i, row in enumerate(ws.iter_rows(values_only=True)):
    rows.append(row)
    if i > 25:   # first 25 rows should be enough
        break

for idx, row in enumerate(rows):
    print(f"Row {idx+1}: {row}")
