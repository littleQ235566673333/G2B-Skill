import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun1/eval_535-20_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun1/eval_535-20_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb['Sheet1']

keyword = '/description'

# Find columns to delete (with 1-based index for openpyxl)
cols_to_delete = []
for idx, cell in enumerate(ws[1], start=1):
    val = str(cell.value) if cell.value is not None else ''
    if keyword in val:
        cols_to_delete.append(idx)

# Delete columns in reverse order to prevent reindexing issues
for col in reversed(cols_to_delete):
    ws.delete_cols(col)

wb.save(output_path)
