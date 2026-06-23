import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-seed0/train/iter_6/regression_gate/before_pass/core_18935/input.xlsx'
wb = openpyxl.load_workbook(input_path)
ws = wb.active

for row in ws.iter_rows(min_row=1, max_row=24, max_col=10, values_only=True):
    print(row)