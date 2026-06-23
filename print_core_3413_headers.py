import openpyxl
input_file = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed2/train/iter_8/regression_gate/before_pass/core_3413/input.xlsx'
wb = openpyxl.load_workbook(input_file)
ws = wb.active
print('Headers:', list(ws.iter_rows(min_row=1, max_row=1, values_only=True))[0])
