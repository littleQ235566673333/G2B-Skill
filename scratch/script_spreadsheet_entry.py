import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_3/regression_gate/before_fix/core_58701/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_3/regression_gate/before_fix/core_58701/output.xlsx'

wb = openpyxl.load_workbook(input_path)
table_ws = wb['Table Tab']
entry_ws = wb['Entry Tab']

# Create mapping from location to office code
location_to_code = {}
for row in table_ws.iter_rows(min_row=2, values_only=True):
    location, office_code = row
    location_to_code[location] = office_code

# Populate office code in column E (E2:E3) based on column B values
for row in range(2, 4):  # E2:E3, locations are in B2:B3
    location_cell = entry_ws[f'B{row}'].value
    code = location_to_code.get(location_cell, '')
    entry_ws[f'E{row}'].value = code

wb.save(output_path)
