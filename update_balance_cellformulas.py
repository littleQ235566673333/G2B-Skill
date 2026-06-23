from openpyxl import load_workbook
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed1/train/iter_7/regression_gate/after_fix/core_56274/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed1/train/iter_7/regression_gate/after_fix/core_56274/output.xlsx'
wb = load_workbook(input_path)
ws = wb["Sheet2"]
# Month headers are in row 3 (Excel 1-based)
# Opening Bal: row 4, Debits: row 5, Credits: row 6, Closing Bal: row 7
row_map = { 'Opening Bal': 4, 'Debits': 5, 'Credits': 6, 'Closing Bal': 7 }
# F:Q has the month columns (6 to 17)
col_start, col_end = 6, 17
col_letters = [chr(64 + i) for i in range(col_start, col_end + 1)]
header_range = f'Sheet2!$F$2:$Q$2'
# D7 on main sheet (presumed Sheet1/active)
ws_main = wb.active
# Create formulas for D9:D12
formula_templates = {
    'D9': f'=INDEX(Sheet2!$F$4:$Q$4, MATCH(D7, {header_range}, 0))',
    'D10': f'=INDEX(Sheet2!$F$5:$Q$5, MATCH(D7, {header_range}, 0))',
    'D11': f'=INDEX(Sheet2!$F$6:$Q$6, MATCH(D7, {header_range}, 0))',
    'D12': f'=INDEX(Sheet2!$F$7:$Q$7, MATCH(D7, {header_range}, 0))',
}
for cell, fmla in formula_templates.items():
    ws_main[cell] = fmla
wb.save(output_path)
