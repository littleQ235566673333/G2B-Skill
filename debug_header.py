import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_TIME-A/eval_250-20_tc1/input.xlsx'

wb = openpyxl.load_workbook(input_path)
sheet = wb['RNM']

rows = list(sheet.iter_rows(min_row=1, max_row=2, min_col=1, max_col=10, values_only=True))
header = rows[0]
print('HEADER:', header)
print('FIRST DATA ROW:', rows[1])
