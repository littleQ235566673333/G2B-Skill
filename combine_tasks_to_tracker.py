import pandas as pd
import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_6/group_60-7/r2/evolve_60-7/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_6/group_60-7/r2/evolve_60-7/output.xlsx'

# Load DataFrames
existing = pd.read_excel(input_path, sheet_name='Existing Task')
additions = pd.read_excel(input_path, sheet_name='Additions')
retired = pd.read_excel(input_path, sheet_name='Retired')

# Combine Existing Task and Additions
combined = pd.concat([existing, additions], ignore_index=True)

# Remove exact matches from Retired (net subtraction)
final = combined.merge(retired.drop_duplicates(), indicator=True, how='left')
final = final[final['_merge'] == 'left_only'].drop(columns=['_merge'])

# Load workbook
wb = openpyxl.load_workbook(input_path)
sheet = wb['Consolidated Tracker']

# Write final output starting from A3. Assumes columns to be written from A to E and header is already present.
for r_idx, row in enumerate(final.itertuples(index=False), start=3):
    for c_idx, value in enumerate(row, start=1):
        sheet.cell(row=r_idx, column=c_idx, value=value)

wb.save(output_path)
