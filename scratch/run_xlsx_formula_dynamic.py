import openpyxl

# Open the input workbook
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/eval/eval_42515_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/eval/eval_42515_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb.active  # Assume data is in the first sheet

# Insert the dynamic formula into F5:F19
for row in range(5, 20):
    formula = f'SUM(1/((1/B{row})*INDIRECT("B"&(ROW()+3))))'
    ws[f'F{row}'].value = f'={formula}'

# Save the workbook
wb.save(output_path)
