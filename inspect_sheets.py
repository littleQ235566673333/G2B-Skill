import pandas as pd

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-pilot-v3/train/iter_1/regression_gate/before_pass/core_9726/input.xlsx'
sheets = pd.read_excel(input_path, sheet_name=None)

print('Sheet names:', list(sheets.keys()))
for name, df in sheets.items():
    print(f'--- {name} ---')
    print('Columns:', df.columns.tolist())
    print(df.head())
