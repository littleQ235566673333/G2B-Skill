import openpyxl
input_file = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed2/train/iter_8/regression_gate/before_pass/core_3413/input.xlsx'
wb = openpyxl.load_workbook(input_file)
ws = wb.active
for i in range(1, 5):
    print(f'Row {i}:', list(ws.iter_rows(min_row=i, max_row=i, values_only=True))[0])
