import pandas as pd
input_file = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-pilot/train/iter_2/group_47766/r2/evolve_47766/input.xlsx'
df = pd.read_excel(input_file)
print(df.iloc[7:37].to_string())
print(df.iloc[40:58].to_string())
print(df.iloc[61:74].to_string())
