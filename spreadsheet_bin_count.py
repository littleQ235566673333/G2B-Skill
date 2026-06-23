import openpyxl
from openpyxl.styles import Border, Side, Font

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0-PRUNED/eval_seed42/eval_39903_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0-PRUNED/eval_seed42/eval_39903_tc1/output.xlsx'

# Load workbook and worksheet
wb = openpyxl.load_workbook(input_path)
ws = wb.active

# Setup font and border
font = Font(name='Courier New', size=9)
side = Side(style='thin')
border = Border(left=side, right=side, top=side, bottom=side)

# Cells C2 to C6
for row in range(2, 7):
    cell = ws[f'C{row}']
    value = cell.value
    count = 0
    if value:
        # Split by comma, semicolon, or space for multiple locations (if necessary)
        locations = [loc.strip() for loc in value.split(',')]
        unique_bins = set()
        for loc in locations:
            # The format is <bin>:<qty>
            if ':' in loc:
                bin_loc = loc.split(':')[0].strip()
                # Exclude bins starting with 'X' or 'Z'
                if not (bin_loc.startswith('X') or bin_loc.startswith('Z')):
                    unique_bins.add(bin_loc)
        count = len(unique_bins)
    # Write count to cell
    cell.value = count
    cell.font = font
    cell.border = border

wb.save(output_path)
print('Done.')
