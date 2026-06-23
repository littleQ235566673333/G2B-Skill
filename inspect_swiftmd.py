import pandas as pd

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/train/iter_1/group_91-34/r1/evolve_91-34/input.xlsx'
sheet_name = 'SwiftMD'

df = pd.read_excel(input_path, sheet_name=sheet_name, header=None)
# Print top 10 rows and 15 columns (header guess)
print('Top 10 rows, 15 columns:')
print(df.iloc[:10, :15])
