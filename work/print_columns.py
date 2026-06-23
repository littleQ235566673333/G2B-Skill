import pandas as pd
input_path = 'results/base_trajectories/master_0_heldout_42/spreadsheet/gpt-4.1/91-34/input.xlsx'
sheetname = 'SwiftMD'
df = pd.read_excel(input_path, sheet_name=sheetname, engine='openpyxl')
print(df.columns.tolist())
