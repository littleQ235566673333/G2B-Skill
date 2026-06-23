import openpyxl

# Paths
input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/eval_seed42/eval_183-8_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/eval_seed42/eval_183-8_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb['Sheet1']

# Place formulas in J3:L6 as requested (but typically weighted average is single formula in a summary row!)
# User wants formulas for weighted avg for columns J,K,L, using weights in column I
for col in ['J', 'K', 'L']:
    formula = f"=ROUND(SUMPRODUCT({col}3:{col}6,$I$3:$I$6)/SUM($I$3:$I$6), 4)"
    ws[f'{col}7'].value = formula  # Place formula in row 7 as a summary

wb.save(output_path)
