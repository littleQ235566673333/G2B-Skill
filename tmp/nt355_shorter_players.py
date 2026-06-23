import pandas as pd
import re

input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/train/iter_7/regression_gate/after_fix/core_nt-355/input.csv'
output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/train/iter_7/regression_gate/after_fix/core_nt-355/output.txt'

df = pd.read_csv(input_path)

# Identify correct columns
name_col = None
height_col = None
for col in df.columns:
    if 'name' in col.lower() or 'player' in col.lower():
        name_col = col
    if 'height' in col.lower():
        height_col = col
assert name_col is not None and height_col is not None

# Helper to convert height in ft/inch (e.g., 6' 1") to inches
pattern = re.compile(r"^(\d+)' (\d+)")
def parse_height(s):
    m = pattern.match(str(s).strip())
    if m:
        ft = int(m.group(1))
        inch = int(m.group(2))
        return ft * 12 + inch
    return None

df['parsed_height'] = df[height_col].apply(parse_height)

# Taylor Kelly reference
taylor_row = df[df[name_col].str.strip().str.lower() == 'taylor kelly']
taylor_height = taylor_row['parsed_height'].iloc[0]

# Find all others shorter than 6' 3" (i.e., < 75 inches)
threshold_inches = 6 * 12 + 3
below_threshold = df[(df['parsed_height'] < threshold_inches)]
# Exclude Taylor Kelly
below_threshold = below_threshold[df[name_col].str.strip().str.lower() != 'taylor kelly']

other_shorter_players = below_threshold[name_col].dropna().tolist()

with open(output_path, 'w', encoding='utf-8') as f:
    for player in other_shorter_players:
        f.write(str(player) + '\n')
