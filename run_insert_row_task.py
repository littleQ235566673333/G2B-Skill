import openpyxl

# File paths
input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42_rerun2/eval_370-43_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42_rerun2/eval_370-43_tc1/output.xlsx'

# Load workbook and sheet
wb = openpyxl.load_workbook(input_path)
ws = wb['Before Insert Row']

# Find all target rows (A7:A1000, 1-indexed rows 7-1000)
rows_to_check = range(7, 1001)
rows_to_insert = []
for row in rows_to_check:
    val = ws[f'A{row}'].value
    if val == 'X':
        rows_to_insert.append(row)

# Insert rows from the bottom up to not mess with indexing
for row in reversed(rows_to_insert):
    ws.insert_rows(row)

# Save result
wb.save(output_path)
