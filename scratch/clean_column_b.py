import openpyxl
import re

input_path = "results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_7/regression_gate/after_pass/core_290-27/input.xlsx"
output_path = "results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_7/regression_gate/after_pass/core_290-27/output.xlsx"

wb = openpyxl.load_workbook(input_path)
ws = wb.active

def clean_b(val):
    if isinstance(val, str):
        m = re.match(r'^([A-Z]{2,3}) ?(\d+)$', val)
        if m:
            return m.group(2)
        else:
            return val
    return val

for row in ws.iter_rows(min_row=14, max_row=137, min_col=2, max_col=2):
    for cell in row:
        cell.value = clean_b(cell.value)

wb.save(output_path)
