import openpyxl
from openpyxl.styles import Font, Border, Side

input_path = "results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun1/eval_39903_tc1/input.xlsx"
output_path = "results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun1/eval_39903_tc1/output.xlsx"

wb = openpyxl.load_workbook(input_path)
ws = wb.active

# Set up borders and font
border = Border(left=Side(style='thin'),
               right=Side(style='thin'),
               top=Side(style='thin'),
               bottom=Side(style='thin'))
font = Font(name='Courier New', size=9)

def count_bin_locations(cell_value):
    # Split by comma or (if no commas) treat as one position per colon
    # Example: A-01-A-02-C-04.D: 5
    if not cell_value or cell_value.strip() == '':
        return 0
    # Split based on appearances of ':[number]' pattern
    import re
    matches = re.findall(r'([^,]+):\s*\d+', cell_value)
    # Remove whitespace
    matches = [m.strip() for m in matches]
    # Exclude if startswith 'X' or 'Z'
    valid_bins = set()
    for m in matches:
        if not (m.startswith('X') or m.startswith('Z')):
            valid_bins.add(m)
    return len(valid_bins)

for row in range(2, 7):
    cell = ws[f'C{row}']
    result = count_bin_locations(str(cell.value))
    cell.value = result
    cell.font = font
    cell.border = border

wb.save(output_path)
