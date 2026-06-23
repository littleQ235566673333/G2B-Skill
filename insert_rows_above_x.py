import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun1/eval_370-43_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun1/eval_370-43_tc1/output.xlsx'
sheetname = 'Before Insert Row'
start_row = 7
end_row = 1000
col_a = 1  # Column A

# Load workbook and select sheet
wb = openpyxl.load_workbook(input_path)
sheet = wb[sheetname]

# Gather rows to insert above (from bottom-up to avoid shifting issues)
rows_to_insert = []
for row_idx in range(start_row, end_row + 1):
    val = sheet.cell(row=row_idx, column=col_a).value
    if val == 'X':
        rows_to_insert.append(row_idx)

# Insert rows from bottom to top
for insert_row in reversed(rows_to_insert):
    sheet.insert_rows(insert_row)

# Save the workbook to output
wb.save(output_path)
