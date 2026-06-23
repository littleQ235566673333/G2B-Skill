import pandas as pd
from openpyxl import load_workbook
import sys

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-seed0/train/iter_1/group_547-43/r0/evolve_547-43/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-seed0/train/iter_1/group_547-43/r0/evolve_547-43/output.xlsx'

# Read all sheets
ds = pd.read_excel(input_path, sheet_name=None)

emp_sheet, lookup_sheet = None, None
for sname in ds:
    if 'emp' in sname.lower():
        emp_sheet = sname
    if 'lookup' in sname.lower():
        lookup_sheet = sname
if not emp_sheet or not lookup_sheet:
    raise ValueError('Missing Emp or lookup sheet!')
df_emp = ds[emp_sheet]
df_lookup = ds[lookup_sheet]

comp_col = None
for col in df_emp.columns:
    if 'comp1' in str(col).lower():
        comp_col = col
        break
if comp_col is None:
    raise ValueError('Comp1-performance column not found!')

fixed_vars = [c for c in df_emp.columns if c != comp_col]
long_df = df_emp.melt(id_vars=fixed_vars, value_vars=[comp_col], var_name='measure', value_name='value')

# --- DEBUG PRINT ---
print('Emp columns:', list(df_emp.columns))
print('Lookup columns:', list(df_lookup.columns))
merge_on = [col for col in fixed_vars if col in df_lookup.columns]
print('Columns to merge on:', merge_on)
long_df.to_csv('debug_long_df.csv', index=False)
df_lookup.to_csv('debug_lookup.csv', index=False)
