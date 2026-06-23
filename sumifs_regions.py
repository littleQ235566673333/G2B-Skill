import openpyxl
import pandas as pd

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_TIME-A/eval_48365_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_TIME-A/eval_48365_tc1/output.xlsx'

# Load workbook and dashboard
wb = openpyxl.load_workbook(input_path)
ds = wb['Dashboard']

# Read selected product
product = ds['C2'].value
# Read region selection from C11, C12, C13
regions = [ds['C11'].value, ds['C12'].value, ds['C13'].value]
regions = [r for r in regions if r]

# Read data sheet into pandas
# Columns: Product, Region, M1
df = pd.read_excel(input_path, sheet_name='Data')

# SUMIFS logic, handling 'All' or blank region selections
if not regions or 'All' in regions:
    mask = df['Product'] == product
else:
    mask = (df['Product'] == product) & (df['Region'].isin(regions))

result = df.loc[mask, 'M1'].sum()

# Write to Dashboard!C4
# openpyxl uses 1-based indexes; C4 = col=3, row=4
ds.cell(row=4, column=3, value=result)
wb.save(output_path)
