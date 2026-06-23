import openpyxl
from datetime import datetime, timedelta

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_7/regression_gate/after_pass/core_41589/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_7/regression_gate/after_pass/core_41589/output.xlsx'

# Load workbook and sheet
wb = openpyxl.load_workbook(input_path)
sheet = wb['Contact List']

# Get values from H4 and I4
last_contact_cell = sheet['H4'].value
response_cell = str(sheet['I4'].value).strip().upper() if sheet['I4'].value else ''

# Prepare logic
result = 'NO ACTION'
if last_contact_cell and response_cell == 'YES':
    try:
        # Ensure H4 is a date
        if isinstance(last_contact_cell, datetime):
            contact_date = last_contact_cell
        else:
            contact_date = datetime.strptime(str(last_contact_cell), '%Y-%m-%d')  # Try ISO format
        days_diff = (datetime.now() - contact_date).days
        if days_diff <= 30:
            result = 'HOLD'
        else:
            result = 'TOUCH BASE'
    except Exception:
        # Invalid date format
        result = 'NO ACTION'

sheet['J4'].value = result
wb.save(output_path)
