import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_4/group_290-1/r0/evolve_290-1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_4/group_290-1/r0/evolve_290-1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb.active

for row in ws.iter_rows(min_row=2, max_row=10, min_col=11, max_col=21, values_only=True):
    print(row)
