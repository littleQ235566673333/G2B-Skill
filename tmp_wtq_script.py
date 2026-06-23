import pandas as pd
import re

def height_to_inches(h):
    if pd.isna(h):
        return None
    m = re.match(r"(\d+)' ?(\d+)", str(h).strip())
    if m:
        return int(m.group(1)) * 12 + int(m.group(2))
    return None

# Read CSV
df = pd.read_csv('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/train/iter_5/group_nt-355/r0/evolve_nt-355/input.csv')

# Find the height column
height_col = None
for col in df.columns:
    if 'height' in col.lower() or any(re.match(r"(\d+)' ?(\d+)", str(val).strip()) for val in df[col].dropna()):
        height_col = col
        break

if not height_col:
    raise Exception('Cannot find height column')

# Standard: 6' 3" = 75 inches
target_height = 6 * 12 + 3

df['__height_inches'] = df[height_col].map(height_to_inches)

# Exclude Taylor Kelly

def is_taylor_kelly(row):
    return any(str(val).strip().lower() == 'taylor kelly' for val in row)

shorter = df[(df['__height_inches'] < target_height) & (df['__height_inches'].notna()) & (~df.apply(is_taylor_kelly, axis=1))]

# Output names from Player or Name or 1st column
name_col = None
for c in ['Player', 'Name']:
    if c in df.columns:
        name_col = c
        break
if not name_col:
    name_col = df.columns[0]

ans = shorter[name_col].drop_duplicates().astype(str)
with open('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/train/iter_5/group_nt-355/r0/evolve_nt-355/output.txt', 'w', encoding='utf-8') as f:
    for a in ans:
        f.write(a + '\n')
