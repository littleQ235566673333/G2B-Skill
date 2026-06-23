import openpyxl
import pandas as pd
from datetime import datetime

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed0/train/iter_8/regression_gate/before_pass/core_9726/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed0/train/iter_8/regression_gate/before_pass/core_9726/output.xlsx'

# Load Excel sheet names
def guess_col(cols, targets):
    for t in targets:
        for c in cols:
            if t.lower() in str(c).lower():
                return c
    return None

xls = pd.ExcelFile(input_path)
sheets = xls.sheet_names
# Table 1 and Table 2 are in order
if len(sheets) >= 2:
    table1_sheet, table2_sheet = sheets[0], sheets[1]
else:
    table1_sheet = table2_sheet = sheets[0]
df1 = pd.read_excel(input_path, sheet_name=table1_sheet)
df2 = pd.read_excel(input_path, sheet_name=table2_sheet)

student_col1 = guess_col(df1.columns, ['student', 'id', 'name'])
visit_date_col = guess_col(df1.columns, ['visit date', 'visit'])
student_col2 = guess_col(df2.columns, ['student', 'id', 'name'])
subm_date_col = guess_col(df2.columns, ['submission date', 'subm', 'date'])

# Ensure datetime
df1[visit_date_col] = pd.to_datetime(df1[visit_date_col], errors='coerce')
df2[subm_date_col] = pd.to_datetime(df2[subm_date_col], errors='coerce')

def find_prior_visit(row):
    stu = row[student_col2]
    subm = row[subm_date_col]
    mask = (df1[student_col1] == stu) & (df1[visit_date_col] < subm)
    visits = df1.loc[mask, visit_date_col]
    if visits.empty or pd.isna(subm):
        return None
    return visits.max()

prior_visits = df2.apply(find_prior_visit, axis=1)

# Open with openpyxl, write result to J2 down
wb = openpyxl.load_workbook(input_path)
ws = wb[table2_sheet]

for i, val in enumerate(prior_visits, start=2):
    cell = ws[f'J{i}']
    if pd.notna(val) and val is not None:
        cell.value = val.strftime('%d-%b-%y')
    else:
        cell.value = None

wb.save(output_path)
