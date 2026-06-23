import pandas as pd
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-smoke16/train/iter_2/regression_gate/after_pass/core_9726/input.xlsx'
sheets = pd.read_excel(input_path, sheet_name=None)
print(list(sheets.keys()))
for name, df in sheets.items():
    print(f'Sheet: {name} Columns: {df.columns.tolist()} Rows: {df.shape[0]}')
    print(df.head())
