import openpyxl

wb = openpyxl.load_workbook('results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42/eval_374-18_tc1/input.xlsx')
ws = wb['Sheet1']

for row in ws.iter_rows(min_row=1, max_col=7, values_only=True):
    print(row)
