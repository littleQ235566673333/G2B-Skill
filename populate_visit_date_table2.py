import openpyxl
import pandas as pd
from datetime import datetime

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed0/train/iter_4/regression_gate/after_pass/core_9726/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed0/train/iter_4/regression_gate/after_pass/core_9726/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb.active

df = pd.read_excel(input_path, header=None)
# Table 1: cols 0,1,2; header is row 0; ends at first full NaN in these cols
rows_1 = []
for i in range(1, len(df)):
    if all(pd.isna(x) for x in df.loc[i, [0, 1, 2]]):
        break
    rows_1.append(i)
Table1 = df.loc[rows_1, [0, 1, 2]]
Table1.columns = ['Student', 'Visit number', 'Visit date']
Table1 = Table1.reset_index(drop=True)

# Table 2: cols 7,8,9; header is row 0; ends at first full NaN in these cols
rows_2 = []
for i in range(1, len(df)):
    if all(pd.isna(x) for x in df.loc[i, [7, 8, 9]]):
        break
    rows_2.append(i)
Table2 = df.loc[rows_2, [7, 8, 9]]
Table2.columns = ['Student', 'Submission date', 'Visit date']
Table2 = Table2.reset_index(drop=True)
# parse dates
Table1['Visit date'] = pd.to_datetime(Table1['Visit date'], errors='coerce')
Table2['Submission date'] = pd.to_datetime(Table2['Submission date'], errors='coerce')

def get_last_visit(row):
    student = row['Student']
    sub_date = row['Submission date']
    visits = Table1[(Table1['Student'] == student) & (Table1['Visit date'] < sub_date)]['Visit date']
    if not visits.empty:
        return visits.max()
    else:
        return pd.NaT
Table2['Visit date'] = Table2.apply(get_last_visit, axis=1)
# Write Table2 visit-dates back to Excel (col index 9, = J; data starts at row 2)
for idx, v in enumerate(Table2['Visit date']):
    cell = ws.cell(row=2+idx, column=10)  # col 10 is 'J'
    if pd.notna(v):
        cell.value = v.strftime('%d-%b-%y')
    else:
        cell.value = None
wb.save(output_path)
