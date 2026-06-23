import openpyxl

# Load the workbook and worksheets
wb = openpyxl.load_workbook('results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-U-N3-seed1/train/iter_7/group_48975/r1/evolve_48975/input.xlsx')
ws_in = wb['Input']
ws_out = wb['Output']

# The header is on row 7. Data rows are 9 to 12 (inclusive), based on structure printout.
# We want to copy values from columns A (0) and B (1) where col E (4) is 'yes', skipping empty rows/cells.
data_rows = []
for row in ws_in.iter_rows(min_row=9, max_row=12, values_only=True):
    if row[4] == 'yes' and row[0] is not None and row[1] is not None:
        data_rows.append((row[0], row[1]))

# Write results to Output!B11 (B column and C column, start row 11, B11/B12/...)
start_row = 11
col_letters = ['B', 'C']
for r_idx, data in enumerate(data_rows):
    for c_idx, val in enumerate(data):
        ws_out[f'{col_letters[c_idx]}{start_row + r_idx}'] = val

wb.save('results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-U-N3-seed1/train/iter_7/group_48975/r1/evolve_48975/output.xlsx')
