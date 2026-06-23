import openpyxl
from openpyxl.styles import Border, Side, Font

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_TIME-B/eval_39903_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_TIME-B/eval_39903_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb.active

# Define cell border and font
all_border = Border(
    left=Side(border_style='thin', color='000000'),
    right=Side(border_style='thin', color='000000'),
    top=Side(border_style='thin', color='000000'),
    bottom=Side(border_style='thin', color='000000')
)
courier_font = Font(name='Courier New', size=9)

def count_valid_bins(cell_value):
    if not cell_value or not isinstance(cell_value, str):
        return 0
    positions = [part.strip() for part in cell_value.split(',')]  # assuming comma separated; adapt if different
    count = 0
    for pos in positions:
        if ':' not in pos:
            continue
        bin_loc = pos.split(':')[0].strip()
        if bin_loc and not (bin_loc.startswith('X') or bin_loc.startswith('Z')):
            count += 1
    return count

for row in range(2, 7):  # C2 to C6
    cell = ws[f'C{row}']
    count = count_valid_bins(cell.value)
    cell.value = count
    cell.font = courier_font
    cell.border = all_border

wb.save(output_path)
