import openpyxl

# Load the input workbook and sheets
input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42/eval_45063_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42/eval_45063_tc1/output.xlsx'
wb = openpyxl.load_workbook(input_path)
sheet1 = wb['Sheet1']
sheet2 = wb['Sheet2']

# Read out-of-stock products from Sheet1!A2:A6
out_of_stock = [sheet1[f'A{row}'].value for row in range(2, 7)]

# Create a lookup for Sheet2 (Product -> Quantity Sold)
items_sheet2 = {}
for row in range(2, sheet2.max_row + 1):
    product = sheet2[f'A{row}'].value
    qty_sold = sheet2[f'B{row}'].value
    items_sheet2[product] = qty_sold

# Populate Sheet1!B2:B6 with the sold quantity or empty string
for idx, item in enumerate(out_of_stock, start=2):
    sold_qty = items_sheet2.get(item, '')
    sheet1[f'B{idx}'].value = sold_qty

# Save result to output file
wb.save(output_path)
