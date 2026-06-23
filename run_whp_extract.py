import openpyxl
import pandas as pd

# File paths
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/train/iter_5/group_54474/r2/evolve_54474/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/train/iter_5/group_54474/r2/evolve_54474/output.xlsx'

# Load workbook
wb = openpyxl.load_workbook(input_path)
ws_whp = wb['WHP']

# Use the correct sheet name (as listed)
whpdata_df = pd.read_excel(input_path, sheet_name='WHP DATA')

# Find site names in WHP tab (E7 and E8)
site_cells = ['E7', 'E8']
site_names = [ws_whp[cell].value for cell in site_cells]

# Determine which columns to extract; assume first is site key, next three are required
columns = list(whpdata_df.columns)
props_to_extract = columns[1:4]  # change as needed for correct columns

# For each site, lookup its data and write results
for i, site in enumerate(site_names):
    if pd.isna(site) or not site:
        continue
    match_row = whpdata_df[whpdata_df[columns[0]] == site]
    if not match_row.empty:
        values = match_row.iloc[0][props_to_extract].values.tolist()
        for j, val in enumerate(values):
            ws_whp.cell(row=7 + i, column=5 + j, value=val)

wb.save(output_path)
print('Done')
