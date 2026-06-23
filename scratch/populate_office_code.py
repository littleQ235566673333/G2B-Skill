import openpyxl

# Paths
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_9/regression_gate/after_fix/core_58701/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_9/regression_gate/after_fix/core_58701/output.xlsx'

# Load workbook and tabs
wb = openpyxl.load_workbook(input_path)
entry_ws = wb['Entry Tab']
table_ws = wb['Table Tab']

# Build location to office code mapping from Table Tab
location_office = {}
for row in table_ws.iter_rows(min_row=2, values_only=True):
    location, office_code = row[:2]
    if location is not None and office_code is not None:
        location_office[str(location).strip()] = str(office_code).strip()

# For each location in Entry Tab, fill office code in E2:E3
for row in range(2, 4):
    location_cell = entry_ws[f'B{row}']
    office_code_cell = entry_ws[f'E{row}']
    location = location_cell.value
    if location is not None and str(location).strip() in location_office:
        office_code_cell.value = location_office[str(location).strip()]
    else:
        office_code_cell.value = ''

wb.save(output_path)