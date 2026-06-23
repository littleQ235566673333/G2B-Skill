import openpyxl
from datetime import datetime, timedelta

# Load workbook and worksheet
wb = openpyxl.load_workbook('results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/train/iter_6/regression_gate/after_pass/core_41589/input.xlsx')
ws = wb['Contact List']

today = datetime.today()

for row in ws.iter_rows(min_row=4, min_col=8, max_col=10):
    h_val = row[0].value  # Column H
    i_val = row[1].value  # Column I
    # Determine the difference in days, if possible
    if isinstance(h_val, datetime):
        days_diff = (today - h_val).days
    else:
        try:
            h_val_date = datetime.strptime(str(h_val), '%Y-%m-%d')
            days_diff = (today - h_val_date).days
        except Exception:
            days_diff = None
    # Apply logic to populate J
    if days_diff is not None and i_val and str(i_val).strip().upper() == 'YES':
        if days_diff <= 30:
            row[2].value = 'HOLD'
        else:
            row[2].value = 'TOUCH BASE'
    else:
        row[2].value = 'NO ACTION'

# Save the result
wb.save('results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/train/iter_6/regression_gate/after_pass/core_41589/output.xlsx')
