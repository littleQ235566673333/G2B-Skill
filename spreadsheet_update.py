import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_8/regression_gate/before_pass/core_302-1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_8/regression_gate/before_pass/core_302-1/output.xlsx'

# Load the workbook and required sheets
wb = openpyxl.load_workbook(input_path)
sheet1 = wb['SHEET1']
sheet2 = wb['SHEET2']
items = wb['ITEMS']

# Helper to read column B (starting from row 2) as a list from a worksheet
def get_column_b(ws, max_row):
    return [ws[f'B{row}'].value for row in range(2, max_row+1)]

# Get the maximum relevant rows from user (SHEET1: B2:B8, SHEET2: B2:B7)
sheet1_n = 8  # up to row 8
sheet2_n = 7  # up to row 7
max_item_row = max(sheet1_n, sheet2_n)

# Read column B from ITEMS (use enough rows for both SHEET1 and SHEET2)
items_b = get_column_b(items, max_item_row)

# Replace Sheet1 B2:B8
for i, val in enumerate(items_b[:sheet1_n-1]):  # -1 because B2 is row 2, B8 is row 8 -> 7 values
    cell = sheet1[f'B{2+i}']
    cell.value = val

# Replace Sheet2 B2:B7
for i, val in enumerate(items_b[:sheet2_n-1]):
    cell = sheet2[f'B{2+i}']
    cell.value = val

wb.save(output_path)
