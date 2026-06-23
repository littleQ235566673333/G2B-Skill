import pandas as pd

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed1/train/iter_7/regression_gate/after_fix/core_38985/input.xlsx'

sheets = pd.read_excel(input_path, sheet_name=None)
for sheet_name, df in sheets.items():
    print(f"Sheet: {sheet_name}\n{df.head(12)}\n\n")
