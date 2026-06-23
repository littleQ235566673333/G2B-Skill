import pandas as pd
import re

# Load data
df = pd.read_csv('results/runs/skillgrad_gpt-4.1_wtq-gpt41/eval_seed1/eval_nt-22_tc1/input.csv')

# Filter for ships in Auckland
auckland_ships = df[df['Port'].astype(str).str.lower().str.contains('auckland', na=False)].copy()

# Extract knot speed from 'Propulsion' column

def extract_speed_knots(prop):
    if pd.isna(prop):
        return None
    # Look for '8 knots', '10 knots', '9 knots', or similar, extract the numeric part
    m = re.search(r'(\d{1,2})(?: knots| knot)', prop)
    if m:
        return float(m.group(1))
    return None

auckland_ships['speed_knots'] = auckland_ships['Propulsion'].apply(extract_speed_knots)

# Find the maximum speed
max_speed = auckland_ships['speed_knots'].max()
# Find ship(s) with that speed
fastest = auckland_ships[auckland_ships['speed_knots'] == max_speed]['Name'].tolist()

with open('results/runs/skillgrad_gpt-4.1_wtq-gpt41/eval_seed1/eval_nt-22_tc1/output.txt', 'w', encoding='utf-8') as f:
    for name in fastest:
        f.write(f"{name}\n")
