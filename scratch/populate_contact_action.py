from openpyxl import load_workbook
from datetime import datetime

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_9/regression_gate/before_pass/core_41589/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_9/regression_gate/before_pass/core_41589/output.xlsx'

wb = load_workbook(input_path)
sheet = wb['Contact List']

h4 = sheet['H4'].value
i4 = str(sheet['I4'].value).strip().upper() if sheet['I4'].value is not None else ''
result = 'NO ACTION'

today = datetime.today()
if isinstance(h4, datetime) and i4 == 'YES':
    days_diff = (today - h4).days
    if days_diff <= 30:
        result = 'HOLD'
    else:
        result = 'TOUCH BASE'

sheet['J4'] = result
wb.save(output_path)
