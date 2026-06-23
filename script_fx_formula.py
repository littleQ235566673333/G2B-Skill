import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_seed1/eval_42515_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_seed1/eval_42515_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb.active

# F5:F19 (rows 5 to 19 inclusive)
for i, row in enumerate(range(5, 20)):
    # $B$8, $B$13, $B$18... increment by 5 each time, starting from 8
    ref_row = 8 + 5 * i
    formula = f"=SUM(1/((1/B{row})*$B${ref_row}))"
    ws[f'F{row}'] = formula

wb.save(output_path)
