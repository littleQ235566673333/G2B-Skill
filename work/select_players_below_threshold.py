import pandas as pd
import numpy as np
import re

df = pd.read_csv('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/train/iter_8/regression_gate/after_fix/core_nt-355/input.csv')

# Clean column names for safe access
columns = [c.strip().lower() for c in df.columns]
df.columns = columns

# Find required columns
height_col = None
player_col = None
for c in columns:
    if 'height' in c:
        height_col = c
    if 'player' in c or 'name' in c:
        player_col = c
assert height_col is not None, 'No height column found.'
assert player_col is not None, 'No player/name column found.'

def parse_height(h):
    if pd.isna(h):
        return np.nan
    m = re.match(r"(\d+)'\s*(\d+)", str(h).strip())
    if m:
        feet, inches = int(m.group(1)), int(m.group(2))
        return feet * 12 + inches
    else:
        return np.nan

# Get Taylor Kelly's height
taylor_row = df[df[player_col].str.strip().str.lower() == "taylor kelly"]
if len(taylor_row) == 0:
    raise Exception('No Taylor Kelly found.')
taylor_height_str = taylor_row.iloc[0][height_col]
taylor_height = parse_height(taylor_height_str)

# Threshold: 6' 3" => 75 inches
threshold = 6 * 12 + 3

# Select ALL other entities (not Taylor Kelly) where height < threshold
filtered = df[df[player_col].str.strip().str.lower() != 'taylor kelly'].copy()
filtered['_height_inches'] = filtered[height_col].map(parse_height)
matches = filtered[filtered['_height_inches'] < threshold][player_col].dropna().tolist()

with open('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/train/iter_8/regression_gate/after_fix/core_nt-355/output.txt', 'w', encoding='utf-8') as f:
    for m in matches:
        f.write(str(m) + '\n')
