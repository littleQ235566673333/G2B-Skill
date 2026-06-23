import openpyxl
wb = openpyxl.load_workbook('results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_1/regression_gate/before_pass/core_32337/input.xlsx')
ws = wb.active

for row in ws.iter_rows(min_row=1, max_row=3, values_only=True):
    print(row)
