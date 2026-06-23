import openpyxl

# Paths
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_10/regression_gate/after_fix/core_50916/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_10/regression_gate/after_fix/core_50916/output.xlsx'

wb = openpyxl.load_workbook(input_path)
sheet = wb.active

# 1. Build mapping from cycle day to class schedule
cycle_days = {}
for i in range(2, 9):  # A2:A8 are cycle days, C2:H8 are classes
    day = sheet[f'A{i}'].value
    if day is None:
        continue
    classes = [sheet[f'{chr(67 + j)}{i}'].value for j in range(6)]  # C-H
    try:
        day_int = int(day)
        cycle_days[day_int] = classes
    except (TypeError, ValueError):
        continue

# 2. For each student day row (A12:A14), copy classes into C-H
for row in range(12, 15):  # rows 12, 13, 14
    cell_val = sheet[f'A{row}'].value
    try:
        day_int = int(cell_val)
        classes = cycle_days.get(day_int, ['']*6)
        for j, val in enumerate(classes):
            sheet[f'{chr(67 + j)}{row}'].value = val
    except (TypeError, ValueError):
        # Skip or empty row if not a valid integer
        for j in range(6):
            sheet[f'{chr(67 + j)}{row}'].value = ''
        continue

wb.save(output_path)
