from openpyxl import load_workbook

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed2/train/iter_3/regression_gate/before_pass/core_41601/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed2/train/iter_3/regression_gate/before_pass/core_41601/output.xlsx'
wb = load_workbook(input_path)
students_ws = wb['Students']
for row in range(2, 8):  # Rows 2 to 7 inclusive
    student_cell = f'A{row}'
    age_cell = f'E{row}'
    if students_ws[student_cell].value:
        formula = f"=INDIRECT(\"'\"&A{row}&\"'!C2\")"
        students_ws[age_cell] = formula
wb.save(output_path)
print('Done')
