import openpyxl
input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42/eval_50768_tc1/input.xlsx'
wb = openpyxl.load_workbook(input_path)
ws = wb.active
# Print the first 10 rows to inspect headers
for i, row in enumerate(ws.iter_rows(min_row=1, max_row=10)):
    print(f"Row {i+1}: {[cell.value for cell in row]}")