import pandas as pd
input_file = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-pilot-v2/train/iter_3/group_54474/r2/evolve_54474/input.xlsx'
df = pd.read_excel(input_file, sheet_name='WHP DATA', header=None)
print(df.head(10))
