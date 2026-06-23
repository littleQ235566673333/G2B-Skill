import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/eval/eval_55979_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/eval/eval_55979_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
calc_ws = wb['Calc']

# Read item number from Calc!A10
item_number = calc_ws['A10'].value

supplier_found = None
for i in range(1, 4):
    ws = wb[f'Supplier_{i}']
    # Search all cells for the item_number
    for row in ws.iter_rows():
        for cell in row:
            if cell.value == item_number:
                supplier_found = f'Supplier_{i}'
                break
        if supplier_found:
            break
    if supplier_found:
        break

# Write the result (the supplier name or blank if not found)
calc_ws['B7'] = supplier_found if supplier_found else ''

wb.save(output_path)
