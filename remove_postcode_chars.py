import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1-PRUNED/eval_seed42/eval_209-30_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1-PRUNED/eval_seed42/eval_209-30_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
sheet = wb['Data to Import']

for row in range(2, 6067):
    cell = sheet.cell(row=row, column=3)
    val = cell.value
    if isinstance(val, str) and len(val) > 3:
        cell.value = val[:-3]
    elif isinstance(val, str):
        cell.value = ''

wb.save(output_path)
