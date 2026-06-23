import openpyxl

wb = openpyxl.load_workbook('results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r2/eval_567-21_tc1/input.xlsx')
ws = wb['Sheet1']
for i, row in enumerate(ws.iter_rows(min_row=1, max_row=10, values_only=True), 1):
    print(f"Row {i}: {row}")
