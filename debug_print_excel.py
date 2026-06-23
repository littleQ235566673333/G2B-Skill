import openpyxl

# File paths
input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/train/iter_6/evolve_387-16/input.xlsx'
sheet_name = 'Sheet1'

wb = openpyxl.load_workbook(input_path)
ws = wb[sheet_name]

# Extract everything in A1:D18 for debugging
for row in ws.iter_rows(min_row=1, max_row=18, min_col=1, max_col=4, values_only=True):
    print(row)
