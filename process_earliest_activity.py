import openpyxl
from datetime import datetime

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_TIME-A/eval_33157_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_TIME-A/eval_33157_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb['Sheet1']

activity_cols = [(2, 'Activity 1'), (4, 'Activity 2'), (6, 'Activity 3'), (8, 'Activity 4')]

def extract_date(cell_value):
    if not cell_value or not isinstance(cell_value, str):
        return None
    try:
        return datetime.strptime(cell_value[:10], '%d/%m/%Y')
    except Exception:
        return None

for row in ws.iter_rows(min_row=2, max_row=6):
    earliest_date = None
    earliest_activity = None
    for idx, (col_idx, activity_name) in enumerate(activity_cols):
        cell_value = row[col_idx - 1].value  # 0-based indexing
        dt = extract_date(cell_value)
        if dt and (earliest_date is None or dt < earliest_date):
            earliest_date = dt
            earliest_activity = activity_name
    row[10].value = earliest_activity  # Col K (11th, 0-based)

wb.save(output_path)
