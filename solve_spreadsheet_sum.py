import openpyxl
from datetime import datetime

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0-PRUNED/eval_seed42/eval_38823_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0-PRUNED/eval_seed42/eval_38823_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
sheet = wb.active

# Explicit date range based on the preview and example answer
start_date = datetime(2022, 1, 1)
end_date = datetime(2022, 1, 5)

# For each search term in H4:H7
for idx in range(4, 8):
    search_term = sheet[f'H{idx}'].value
    total = 0
    # Iterate through rows containing data (from row 3 onward)
    for row in range(3, sheet.max_row + 1):
        date = sheet[f'A{row}'].value
        fabrics = sheet[f'B{row}'].value
        units = sheet[f'C{row}'].value
        # Only process non-empty and valid rows
        if isinstance(date, datetime) and isinstance(fabrics, str) and isinstance(units, (int, float)):
            if start_date <= date <= end_date and search_term in fabrics:
                total += units
    # Write the result to column I
    sheet[f'I{idx}'] = total

wb.save(output_path)
