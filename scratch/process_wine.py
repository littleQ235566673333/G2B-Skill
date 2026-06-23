import pandas as pd
input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_v6/train/iter_6/group_nt-178/r1/evolve_nt-178/input.csv'
output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_v6/train/iter_6/group_nt-178/r1/evolve_nt-178/output.txt'

tbl = pd.read_csv(input_path)
# Remove rows with unavailable data
mask = tbl['Wine'].astype(str).str.contains('unavailable')
tbl = tbl[~mask]
# Remove 'Canada' summary row
province_col = tbl.columns[0]
tbl = tbl[tbl[province_col].astype(str).str.lower() != 'canada']
# Convert wine column to numeric
wine_col = 'Wine'
tbl[wine_col] = pd.to_numeric(tbl[wine_col], errors='coerce')
# Find the province with max wine consumption
max_idx = tbl[wine_col].idxmax()
top_province = tbl.loc[max_idx, province_col]
with open(output_path, 'w') as f:
    f.write(f'{top_province}\n')
