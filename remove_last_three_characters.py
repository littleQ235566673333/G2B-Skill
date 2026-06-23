import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r2/eval_209-30_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r2/eval_209-30_tc1/output.xlsx'
sheet_name = 'Data to Import'
start_row = 2
end_row = 6066
col = 3  # Column C

wb = openpyxl.load_workbook(input_path)
ws = wb[sheet_name]

for row in range(start_row, end_row + 1):
    cell = ws.cell(row=row, column=col)
    if isinstance(cell.value, str) and len(cell.value) > 3:
        cell.value = cell.value[:-3]
    elif isinstance(cell.value, str):
        cell.value = ''

wb.save(output_path)
