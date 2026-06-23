import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42/eval_42515_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42/eval_42515_tc1/output.xlsx'

# Load the workbook and the first sheet
data_wb = openpyxl.load_workbook(input_path)
sheet = data_wb.active  # or specify by name if needed

# Insert the formula in F5:F19
for row in range(5, 20):
    formula = f'=SUM(1/((1/B{row})*INDIRECT("B"&ROW()+3)))'
    sheet[f'F{row}'].value = formula

# Save the modified workbook
data_wb.save(output_path)
print(f"Formulas placed in F5:F19 and file saved to: {output_path}")