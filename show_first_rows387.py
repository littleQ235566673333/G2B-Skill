import openpyxl
wb = openpyxl.load_workbook('results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-seed0/train/iter_2/group_387-16/r1/evolve_387-16/input.xlsx')
ws = wb['Sheet1']
for i in range(1, 5):
    print([cell.value for cell in ws[i]])
