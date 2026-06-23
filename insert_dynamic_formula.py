import openpyxl

input_path = "results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r3/eval_42515_tc1/input.xlsx"
output_path = "results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r3/eval_42515_tc1/output.xlsx"

# Load workbook
wb = openpyxl.load_workbook(input_path)
ws = wb.active

# Insert dynamic formula into F5:F19
for row in range(5, 20):
    formula = f"=SUM(1/((1/B{row})*OFFSET($B$8,ROW()-ROW($F$5),0)))"
    ws[f"F{row}"].value = formula

wb.save(output_path)
