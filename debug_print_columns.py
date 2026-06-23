import pandas as pd
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed0/train/iter_2/group_387-16/r3/evolve_387-16/input.xlsx'
df = pd.read_excel(input_path, sheet_name='Sheet1', header=0)
print(list(df.columns))
