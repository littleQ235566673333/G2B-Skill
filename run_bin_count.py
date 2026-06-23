import openpyxl
from openpyxl.styles import Border, Side, Font

input_path = "results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/eval_seed42_rerun1/eval_39903_tc1/input.xlsx"
output_path = "results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/eval_seed42_rerun1/eval_39903_tc1/output.xlsx"

# Load workbook and worksheet
wb = openpyxl.load_workbook(input_path)
ws = wb.active

def count_valid_bins(cell_value):
    if not cell_value:
        return 0
    # Each location is like <binloc>: <number>
    # Multiple locations might be separated by comma, semicolon, or newlines
    import re
    # Split using commas, semicolons, or new lines
    items = re.split(r'[;\n,]', str(cell_value))
    count = 0
    for item in items:
        item = item.strip()
        if not item:
            continue
        # Try to extract location using regex: location:amount
        match = re.match(r'([^:]+):\s*\d+', item)
        if match:
            loc = match.group(1).strip()
            if not (loc.startswith('X') or loc.startswith('Z')):
                count += 1
    return count

# Formatting
border = Border(left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin'))
font = Font(name="Courier New", size=9)

for row in range(2, 7):  # C2 to C6
    cell = ws[f'C{row}']
    count = count_valid_bins(cell.value)
    cell.value = count
    cell.border = border
    cell.font = font

wb.save(output_path)
