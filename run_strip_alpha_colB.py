import openpyxl
import re

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-U-N3-seed0/train/iter_8/regression_gate/before_pass/core_290-27/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-U-N3-seed0/train/iter_8/regression_gate/before_pass/core_290-27/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb['Sheet1']

def strip_alpha(val):
    if isinstance(val, str):
        if val.strip() == '':
            return val
        match = re.match(r'^([A-Z]{2,3})(\s?)(\d+)$', val)
        if match:
            return match.group(3)
        # Remove leading 2-3 capital letters + optional spaces (only at start)
        val2 = re.sub(r'^([A-Z]{2,3})\s*', '', val)
        return val2
    return val

for row in ws.iter_rows(min_row=14, max_row=137, min_col=2, max_col=2):
    cell = row[0]
    original = cell.value
    if isinstance(original, str):
        # Attempt conversion to float to exclude numerics
        try:
            float(original)
            continue
        except Exception:
            pass
        cell.value = strip_alpha(original)

wb.save(output_path)
