import openpyxl
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed0/train/iter_6/regression_gate/after_pass/core_18935/input.xlsx'
wb = openpyxl.load_workbook(input_path)
ws = wb.active
for r in range(1,31):
    print([ws.cell(row=r, column=c).value for c in range(1,11)])
