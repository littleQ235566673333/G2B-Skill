import pandas as pd
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed2/train/iter_1/group_91-34/r2/evolve_91-34/input.xlsx'
sheet_name = 'SwiftMD'
df = pd.read_excel(input_path, sheet_name=sheet_name)
print(list(df.columns))
