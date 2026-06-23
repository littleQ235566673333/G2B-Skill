import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42_rerun2/eval_209-30_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42_rerun2/eval_209-30_tc1/output.xlsx'
sheet_name = 'Data to Import'
col = 'C'
start_row = 2
end_row = 6066

# Load the workbook and worksheet
wb = openpyxl.load_workbook(input_path)
ws = wb[sheet_name]

for row in range(start_row, end_row + 1):
    cell = ws[f'{col}{row}']
    value = cell.value
    if isinstance(value, str) and len(value) >= 3:
        cell.value = value[:-3]
    # If less than 3 characters or not a string, leave as is

wb.save(output_path)
