import pandas as pd

input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_1/group_nt-250/r2/evolve_nt-250/input.csv'
output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_1/group_nt-250/r2/evolve_nt-250/output.txt'

df = pd.read_csv(input_path)
# Identify the date column and points column
date_col = df.columns[0]
points_col = [col for col in df.columns if 'point' in col.lower()]
if points_col:
    points_col = points_col[0]
    mask = df[date_col].astype(str).str.strip().str.lower() == '6 february 1922'
    result = df.loc[mask, points_col]
    with open(output_path, 'w', encoding='utf-8') as f:
        for val in result:
            f.write(str(val)+'\n')
else:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('')
