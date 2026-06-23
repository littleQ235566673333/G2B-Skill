import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_TIME-C/eval_45063_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_TIME-C/eval_45063_tc1/output.xlsx'

# Load the workbook and relevant sheets
wb = openpyxl.load_workbook(input_path)
sheet1 = wb['Sheet1']
sheet2 = wb['Sheet2']

# Build a dictionary from Sheet2 (product name -> quantity)
sheet2_products = {}
for row in sheet2.iter_rows(min_row=2, min_col=1, max_col=2):
    name = row[0].value
    qty = row[1].value
    sheet2_products[name] = qty

# Process Sheet1, cells A2:A6
for i in range(2, 7):
    product_name = sheet1[f'A{i}'].value
    qty = sheet2_products.get(product_name, '')
    sheet1[f'B{i}'].value = qty

# Save to output path
wb.save(output_path)
