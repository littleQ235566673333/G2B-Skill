import openpyxl

# Paths (update as per user input)
INPUT_PATH = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/train/iter_7/regression_gate/after_pass/core_41969/input.xlsx'
OUTPUT_PATH = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/train/iter_7/regression_gate/after_pass/core_41969/output.xlsx'

# Open the workbook
wb = openpyxl.load_workbook(INPUT_PATH)
ws = wb.active  # Use the active sheet

# Pattern formulas:
formulas = [
    '=COUNTBLANK(A3:C3)',
    '=COUNTBLANK(D3:F3)',
    '=COUNTBLANK(G3:I3)',
]

# Insert formulas in A6, B6, C6
for col, formula in zip(['A', 'B', 'C'], formulas):
    ws[f'{col}6'] = formula

# Save the workbook
wb.save(OUTPUT_PATH)
