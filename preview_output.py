import openpyxl

# Output details
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-smoke/train/iter_1/group_269-44/r0/evolve_269-44/output.xlsx'
preview = []

wb = openpyxl.load_workbook(output_path)
ws = wb['Sheet1']

for row in range(1, 16):
    val = ws.cell(row=row, column=1).value
    preview.append((row, val))

for row, val in preview:
    print(f"A{row}: {val}")
