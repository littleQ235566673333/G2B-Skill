import openpyxl

wb = openpyxl.load_workbook('results/runs/g2b-v8_gpt-4.1_ss-gpt41/eval_seed1/eval_38823_tc1/input.xlsx')
ws = wb.active
for row in ws.iter_rows(min_row=1, max_row=15, values_only=True):
    print(row)
