import openpyxl
import pandas as pd
from collections import OrderedDict

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed1/eval_seed42_rerun1/eval_57989_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed1/eval_seed42_rerun1/eval_57989_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb.active

df = pd.read_excel(input_path, sheet_name=ws.title, header=None)
# Header row identified previously at index 22
data_start_row = 23
header_row_idx = 22
columns = list(df.iloc[header_row_idx])
# Weekdays columns indices (skipping first nan, which is driver column)
weekday_indices = [i for i, v in enumerate(columns) if isinstance(v, str) and v.strip() != '']
weekdays = [columns[i] for i in weekday_indices]
# Prepare ordered result
results = OrderedDict()
drivers_in_order = []
for i in range(data_start_row, len(df)):
    row = df.iloc[i]
    driver = row[0]
    if pd.isna(driver) or str(driver).strip() == '':
        continue
    driver = str(driver).strip()
    if driver not in results:
        results[driver] = {d: 0 for d in weekdays}
        drivers_in_order.append(driver)
    for j, day in zip(weekday_indices, weekdays):
        val = row[j]
        if not pd.isna(val) and str(val).strip() != '':
            results[driver][day] += 1
# Write output in B25:H43 (drivers row-wise, weekdays col-wise)
start_row = 25
start_col = 2  # 'B' = 2
for i, driver in enumerate(drivers_in_order):
    for j, day in enumerate(weekdays):
        ws.cell(row=start_row + i, column=start_col + j, value=results[driver][day])
wb.save(output_path)
