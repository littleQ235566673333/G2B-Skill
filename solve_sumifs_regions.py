import pandas as pd
from openpyxl import load_workbook

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed0/eval_seed42/eval_48365_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed0/eval_seed42/eval_48365_tc1/output.xlsx'

# Load data from all sheets
sheets = pd.read_excel(input_path, sheet_name=None)
data = sheets['Data']

# Also open workbook for writing result
wb = load_workbook(input_path)
dashboard = wb['Dashboard']

# Read product (single) and region selection (up to 3) from dashboard
product = dashboard['C2'].value
regions = [dashboard['C11'].value, dashboard['C12'].value, dashboard['C13'].value]
regions = [r for r in regions if r is not None and str(r).strip() != '']

# Check if any region is 'All'
if any(str(r).strip().lower() == 'all' for r in regions):
    total = data.loc[data['Product'] == product, 'M1'].sum()
else:
    total = data.loc[(data['Product'] == product) & (data['Region'].isin(regions)), 'M1'].sum()

# Write the result to Dashboard!C4
dashboard['C4'] = total
wb.save(output_path)
