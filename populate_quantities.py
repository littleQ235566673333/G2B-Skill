import openpyxl

# Load the workbook and select sheets
wb = openpyxl.load_workbook('results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/eval_seed42_rerun1/eval_45063_tc1/input.xlsx')
sheet1 = wb['Sheet1']
sheet2 = wb['Sheet2']

# Build lookup dictionary from Sheet2 (product -> quantity sold)
lookup = {}
for row in sheet2.iter_rows(min_row=2, min_col=1, max_col=2, values_only=True):
    product, qty = row
    key = str(product).strip() if product is not None else ''
    lookup[key] = qty

# For out-of-stock items in Sheet1:A2:A6, fill B2:B6 with sold quantity from Sheet2, or empty string
for i in range(2, 7):  # rows 2 to 6 inclusive
    prod = sheet1[f'A{i}'].value
    prod_key = str(prod).strip() if prod is not None else ''
    qty = lookup.get(prod_key, '')
    sheet1[f'B{i}'].value = qty if qty is not None else ''

wb.save('results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/eval_seed42_rerun1/eval_45063_tc1/output.xlsx')
