import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun2/eval_370-43_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun2/eval_370-43_tc1/output.xlsx'
sheet_name = 'Before Insert Row'

# Load workbook and select sheet
wb = openpyxl.load_workbook(input_path)
ws = wb[sheet_name]

# Process from row 1000 to 7 to avoid shifting issues
for row in range(1000, 6, -1):
    cell = ws[f'A{row}'].value
    if cell == 'X':
        ws.insert_rows(row)

# Save results
wb.save(output_path)
