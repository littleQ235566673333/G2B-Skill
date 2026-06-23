import openpyxl

# File paths
input_fp = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42/eval_42515_tc1/input.xlsx'
output_fp = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42/eval_42515_tc1/output.xlsx'

# Load workbook and active sheet
wb = openpyxl.load_workbook(input_fp)
ws = wb.active

# Set formulas for F5:F19
def_col = 'B'
start_row = 5
end_row = 19
for row in range(start_row, end_row + 1):
    formula = f'SUM(1/((1/{def_col}{row})*{def_col}{row + 3}))'
    ws[f'F{row}'].value = f'={formula}'

# Save output
wb.save(output_fp)
print('Formulas written to F5:F19 as requested.')
