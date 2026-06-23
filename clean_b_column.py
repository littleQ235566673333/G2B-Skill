import openpyxl
import re
import datetime

def clean_b_value(v):
    if isinstance(v, datetime.datetime):
        return v
    if v is None:
        return v
    if isinstance(v, (int, float)):
        return v
    s = str(v)
    # extract the first number found (including decimals)
    match = re.search(r'(\d[\d\.]*)', s)
    return match.group(1) if match else v

infile = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-U-N3-seed0/train/iter_4/regression_gate/before_pass/core_290-27/input.xlsx'
outfile = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-U-N3-seed0/train/iter_4/regression_gate/before_pass/core_290-27/output.xlsx'

wb = openpyxl.load_workbook(infile)
ws = wb.active

for row in ws.iter_rows(min_row=14, max_row=137, min_col=2, max_col=2):
    cell = row[0]
    cell.value = clean_b_value(cell.value)

wb.save(outfile)
