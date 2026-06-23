import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_6/regression_gate/after_pass/core_302-1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_6/regression_gate/after_pass/core_302-1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
items_sheet = wb['ITEMS']

# Extract column B from ITEMS (starting from B2)
items_values = [items_sheet[f'B{row}'].value for row in range(2, items_sheet.max_row+1)]

def update_column(sheet_name, dest_end_row):
    sheet = wb[sheet_name]
    for i, value in enumerate(items_values[:dest_end_row-1]):
        cell = sheet[f'B{i+2}']
        if cell.value != value:
            cell.value = value

# SHEET1: B2:B8 maps to 7 values
update_column('SHEET1', 8)
# SHEET2: B2:B7 maps to 6 values
update_column('SHEET2', 7)

wb.save(output_path)
