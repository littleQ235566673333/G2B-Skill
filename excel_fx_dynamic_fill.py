import openpyxl

input_path = "results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/eval_seed42/eval_42515_tc1/input.xlsx"
output_path = "results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/eval_seed42/eval_42515_tc1/output.xlsx"

# Load workbook and the active sheet
gb = openpyxl.load_workbook(input_path)
sheet = gb.active

# Write formula for F5:F19
for row in range(5, 20):
    formula = f"=SUM(1/((1/B{row})*INDEX($B$8:$B$19,{row}-4)))"
    sheet[f"F{row}"].value = formula

gb.save(output_path)
