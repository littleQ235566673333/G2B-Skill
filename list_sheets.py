import openpyxl
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-smoke/train/iter_1/group_269-44/r0/evolve_269-44/input.xlsx'
wb = openpyxl.load_workbook(input_path)
print(wb.sheetnames)