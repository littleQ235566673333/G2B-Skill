import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_seed0/eval_22-47_tc1/input.xlsx'
wb = openpyxl.load_workbook(input_path)
ws = wb.active

data = list(ws.values)
for i, row in enumerate(data[:12]):
    print(f"Row {i}: {row}")
