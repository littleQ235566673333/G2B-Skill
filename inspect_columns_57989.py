import openpyxl
import pandas as pd

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed1/eval_seed42_rerun1/eval_57989_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed1/eval_seed42_rerun1/eval_57989_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb.active

df = pd.read_excel(input_path, sheet_name=ws.title)

header_row = None
weekdays_set = set(['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'])
for i, row in enumerate(df.values):
    row_list = [str(x).lower() if isinstance(x, str) else '' for x in row]
    if any(day in weekdays_set for day in row_list):
        header_row = i
        break
columns = list(df.iloc[header_row])
driver_candidates = [c for c in columns if isinstance(c,str) and c.strip().lower() not in weekdays_set]
print('HEADER ROW:', header_row)
print('COLUMNS:', columns)
print('DRIVER CANDIDATES:', driver_candidates)
