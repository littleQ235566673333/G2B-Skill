import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed1/train/iter_5/regression_gate/after_fix/core_387-16/input.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb['Sheet1']

for row in ws.iter_rows(min_row=1, max_row=5, values_only=True):
    print(row)