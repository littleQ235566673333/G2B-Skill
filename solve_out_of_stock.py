import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed2/eval_seed42_rerun2/eval_45063_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed2/eval_seed42_rerun2/eval_45063_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws1 = wb['Sheet1']
ws2 = wb['Sheet2']

# Read all out-of-stock items (Sheet1 column A, rows 2-6)
search_names = [ws1[f'A{row}'].value for row in range(2, 7)]

# Build product -> sold mapping from Sheet2
lookup = {}
for row in range(2, ws2.max_row + 1):
    prod = ws2[f'A{row}'].value
    qty = ws2[f'B{row}'].value
    if prod is not None:
        # Only use the first encountered (in descending order)
        if prod not in lookup:
            lookup[prod] = qty

# Populate Sheet1 column B (rows 2-6) with sold quantity or empty string
for idx, prod in enumerate(search_names, start=2):
    out = lookup.get(prod, "")
    ws1[f'B{idx}'] = out if out is not None else ""

wb.save(output_path)
