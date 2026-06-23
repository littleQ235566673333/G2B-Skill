import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_8/regression_gate/after_pass/core_32337/input.xlsx'
wb = openpyxl.load_workbook(input_path)
ws = wb.active

# Print headers and first 3 rows
for idx, row in enumerate(ws.iter_rows(min_row=1, max_row=3, values_only=True)):
    print(row)
