import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_8/regression_gate/before_pass/core_41601/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_8/regression_gate/before_pass/core_41601/output.xlsx'

# Load workbook and sheet
wb = openpyxl.load_workbook(input_path)
ws_students = wb['Students']

# List student names from column A (A2:A7)
names = [ws_students[f'A{i}'].value for i in range(2, 8)]

# Compile ages from sheets named after each student
for idx, name in enumerate(names, start=2):
    age = None
    if name and name in wb.sheetnames:
        sheet = wb[name]
        age = sheet['C2'].value
    ws_students[f'E{idx}'] = age

# Save the results to the output file
wb.save(output_path)
