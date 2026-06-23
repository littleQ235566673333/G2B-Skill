from openpyxl import load_workbook

input_file = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_2/regression_gate/before_pass/core_41601/input.xlsx'
output_file = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_2/regression_gate/before_pass/core_41601/output.xlsx'

wb = load_workbook(input_file)
ws_students = wb['Students']

for row in range(2, 8):  # Rows 2-7 (E2:E7)
    student = ws_students[f'A{row}'].value
    if student:
        ws_students[f'E{row}'] = f"='{student}'!C2"
    else:
        ws_students[f'E{row}'] = None

wb.save(output_file)
