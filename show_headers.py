import openpyxl

# File paths
input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/train/iter_6/evolve_387-16/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/train/iter_6/evolve_387-16/output.xlsx'
sheet_name = 'Sheet1'

wb = openpyxl.load_workbook(input_path)
ws = wb[sheet_name]
headers = [ws.cell(row=1, column=i).value for i in range(1, 10)]
print(f"Headers in Sheet1 row 1: {headers}")
