import openpyxl

# Load the workbook
wb = openpyxl.load_workbook('results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-smoke/train/iter_1/regression_gate/after_pass/core_18935/input.xlsx')
print(wb.sheetnames)