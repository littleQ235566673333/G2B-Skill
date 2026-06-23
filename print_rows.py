import openpyxl
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/eval_seed42/eval_56378_tc1/input.xlsx'
wb = openpyxl.load_workbook(input_path)
ws = wb.active

# Print first 20 rows
for row_num in range(1, 21):
    vals = [cell.value for cell in ws[row_num]]
    print(f'ROW {row_num}:', vals)