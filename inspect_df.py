import pandas as pd
from openpyxl import load_workbook
from datetime import datetime

input_file = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-pilot/train/iter_2/group_47766/r2/evolve_47766/input.xlsx'
output_file = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-pilot/train/iter_2/group_47766/r2/evolve_47766/output.xlsx'

# Read all sheets
xls = pd.read_excel(input_file, sheet_name=None)

# We'll use openpyxl for writing
wb = load_workbook(input_file)
ws = wb.active

# Find the data range via pandas
sheetname = ws.title
df = xls[sheetname]

print('Columns:', df.columns.tolist())
print('Head of DataFrame:')
print(df.head(20))
print('Rows 7-37:')
print(df.iloc[7:37])
print('Rows 40-58:')
print(df.iloc[40:58])
print('Rows 61-74:')
print(df.iloc[61:74])
