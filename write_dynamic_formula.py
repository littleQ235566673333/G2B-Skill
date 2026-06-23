import openpyxl

input_path = "results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_seed2/eval_42515_tc1/input.xlsx"
output_path = "results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_seed2/eval_42515_tc1/output.xlsx"

# Load the workbook and select the first worksheet
wb = openpyxl.load_workbook(input_path)
ws = wb.active

# Write the dynamic formula into F5:F19
for i, row in enumerate(range(5, 20)):
    # Construct OFFSET formula: OFFSET($B$8,ROW()-5,0)
    # Your original formula: SUM(1/((1/B5)*$B$8))
    # Dynamic version: SUM(1/((1/B5)*OFFSET($B$8,ROW()-5,0)))
    formula = f"=SUM(1/((1/B{row})*OFFSET($B$8,ROW()-5,0)))"
    cell = f"F{row}"
    ws[cell] = formula

wb.save(output_path)
