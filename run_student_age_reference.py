import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_5/regression_gate/before_pass/core_41601/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_5/regression_gate/before_pass/core_41601/output.xlsx'

wb = openpyxl.load_workbook(input_path)
sheet = wb['Students']

for row in range(2, 8):  # E2:E7, names in A2:A7
    student_name = sheet[f'A{row}'].value
    if student_name and student_name in wb.sheetnames:
        age = wb[student_name]['C2'].value
        sheet[f'E{row}'] = age
    else:
        sheet[f'E{row}'] = None

wb.save(output_path)
