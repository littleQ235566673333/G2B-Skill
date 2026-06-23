import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r3/eval_209-30_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r3/eval_209-30_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb['Data to Import']

for row in ws.iter_rows(min_row=2, max_row=6066, min_col=3, max_col=3):
    for cell in row:
        val = cell.value
        if isinstance(val, str) and len(val) > 3:
            cell.value = val[:-3]
        elif isinstance(val, str):
            cell.value = ''

wb.save(output_path)
