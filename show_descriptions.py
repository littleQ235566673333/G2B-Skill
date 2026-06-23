import openpyxl

# Load workbook and sheet
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/eval_seed42/eval_524-31_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/eval_seed42/eval_524-31_tc1/output.xlsx'
wb = openpyxl.load_workbook(input_path)
sheet = wb['Exp-DB']

# Print the first 10 transaction descriptions to see their format
for i in range(1, 11):
    print(f'Row {i}:', sheet[f'B{i}'].value)