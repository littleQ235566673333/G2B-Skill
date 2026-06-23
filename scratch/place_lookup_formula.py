import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_6/group_36277/r0/evolve_36277/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_6/group_36277/r0/evolve_36277/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb.active

# Place formulas in I2:I5
for i in range(2, 6):  # Rows 2 to 5
    formula = '=INDEX($A$2:$F$6,ROW()-1, MATCH(H{},$A$1:$F$1,0))'.format(i)
    ws[f'I{i}'] = formula

wb.save(output_path)
print('Formulas written to I2:I5.')
