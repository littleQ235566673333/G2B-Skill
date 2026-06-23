import openpyxl

# File paths
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_6/group_57262/r1/evolve_57262/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_6/group_57262/r1/evolve_57262/output.xlsx'

# Load workbook and select active sheet
wb = openpyxl.load_workbook(input_path)
sheet = wb.active

# Define unit prices (customize as needed)
unit_prices = {'F': 8, 'G': 10}

# Process rows 7 to 15
for row in range(7, 16):
    total = 0
    # F column
    qty_f = sheet[f'F{row}'].value or 0
    total += (qty_f if isinstance(qty_f, (int, float)) else 0) * unit_prices['F']
    # G column
    qty_g = sheet[f'G{row}'].value or 0
    total += (qty_g if isinstance(qty_g, (int, float)) else 0) * unit_prices['G']
    # Write to T column
    sheet[f'T{row}'].value = total if total != 0 else None

# Save workbook
wb.save(output_path)
