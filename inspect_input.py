import openpyxl

# Load the workbook and select the sheet
input_path = 'results/runs/g2b-v8_gpt-4.1_ss-gpt41/eval_seed0/eval_183-8_tc1/input.xlsx'
output_path = 'results/runs/g2b-v8_gpt-4.1_ss-gpt41/eval_seed0/eval_183-8_tc1/output.xlsx'
wb = openpyxl.load_workbook(input_path)
ws = wb['Sheet1']

# Print out the first 8 rows for inspection
for row in ws.iter_rows(min_row=1, max_row=8, values_only=True):
    print(row)

# Save the workbook (no changes yet)
wb.save(output_path)
