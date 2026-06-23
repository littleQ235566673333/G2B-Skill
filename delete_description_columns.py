import openpyxl

input_path = 'results/runs/g2b-v8_gpt-4.1_ss-gpt41/eval_seed1/eval_535-20_tc1/input.xlsx'
output_path = 'results/runs/g2b-v8_gpt-4.1_ss-gpt41/eval_seed1/eval_535-20_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb['Sheet1']

# Find columns to delete (marked by '/description' in first row)
cols_to_delete = []
for idx, cell in enumerate(ws[1], start=1):
    if cell.value and '/description' in str(cell.value):
        cols_to_delete.append(idx)
# Must delete from right to left to keep indices stable
for col_idx in reversed(cols_to_delete):
    ws.delete_cols(col_idx)

wb.save(output_path)
