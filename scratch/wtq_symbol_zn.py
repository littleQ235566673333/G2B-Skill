import pandas as pd

df = pd.read_csv('results/base_trajectories/master_0_heldout_42/wtq/gpt-4.1/nt-200/input.csv')

# Identify columns
symb_col = None
num_col = None
for col in df.columns:
    if col.lower().strip() == 'symbol':
        symb_col = col
    if 'number' in col.lower():
        num_col = col

# Find value
if symb_col and num_col:
    idx = df[symb_col].astype(str).str.strip().str.lower() == 'zn'
    result = df.loc[idx, num_col].iloc[0] if idx.any() else ''
else:
    result = ''

with open('results/base_trajectories/master_0_heldout_42/wtq/gpt-4.1/nt-200/output.txt', 'w', encoding='utf-8') as f:
    f.write(str(result) + '\n')
