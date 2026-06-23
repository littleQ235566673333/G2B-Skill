import openpyxl
from openpyxl.styles import Border, Side, Font

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_rerun1/eval_39903_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_rerun1/eval_39903_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb.active

def count_valid_bins(cell_value):
    if not cell_value or not isinstance(cell_value, str):
        return 0
    bins = set()
    for entry in cell_value.split(','):
        entry = entry.strip()
        if ':' in entry:
            loc = entry.split(':')[0].strip()
            if loc and not (loc.startswith('X') or loc.startswith('Z')):
                bins.add(loc)
    return len(bins)

# Style
border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
font = Font(name='Courier New', size=9)

for row in range(2, 7):
    cell = ws[f'C{row}']
    count = count_valid_bins(cell.value)
    cell.value = count
    cell.border = border
    cell.font = font

wb.save(output_path)
