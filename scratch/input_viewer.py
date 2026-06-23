import openpyxl
from datetime import datetime

wb = openpyxl.load_workbook('results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_6/regression_gate/after_fix/core_4714/input.xlsx')
ws = wb['Sheet2']
data = []
rows = ws.iter_rows(values_only=True)
def fmt(val):
    return val.strftime('%Y-%m') if isinstance(val, datetime) else val
i = 0
for row in rows:
    if i > 25:
        break
    data.append([fmt(cell) for cell in row])
    i += 1
for row in data:
    print(row)
