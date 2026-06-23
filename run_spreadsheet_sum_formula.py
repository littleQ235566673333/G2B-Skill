import openpyxl
from datetime import datetime

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/eval_seed42_rerun1/eval_38823_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/eval_seed42_rerun1/eval_38823_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
sheet = wb.active

data_start_row = 3

start_date = sheet['F4'].value
end_date = sheet['G4'].value

for i in range(4, 8):
    search_term = sheet[f'H{i}'].value
    total = 0
    for row in range(data_start_row, sheet.max_row + 1):
        row_date = sheet[f'A{row}'].value
        fabrics = sheet[f'B{row}'].value
        units = sheet[f'C{row}'].value
        # Skip rows with missing values
        if row_date is None or fabrics is None or units is None:
            continue
        # Only process rows with proper datetime
        if not isinstance(row_date, datetime):
            continue
        if start_date and end_date and start_date <= row_date <= end_date and search_term in fabrics:
            total += units
    sheet[f'I{i}'] = total

wb.save(output_path)
