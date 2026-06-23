import pandas as pd
import re
input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/train/iter_7/regression_gate/before_fix/core_nt-355/input.csv'
output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/train/iter_7/regression_gate/before_fix/core_nt-355/output.txt'
df = pd.read_csv(input_path)
# Identify columns
# Find taylor kelly's height and those < 6' 3"
# The question says taylor kelly is shorter than 6' 3", but asks for others also shorter than 6' 3"
def parse_height(s):
    if isinstance(s, str):
        m = re.match(r"^(\d+)'\s*(\d+)", s.strip())
        if m:
            return int(m.group(1)) * 12 + int(m.group(2))
    return None
# Guess column names with 'Height' and 'Player' or similar
height_col = next(c for c in df.columns if 'height' in c.lower())
entity_col = next(c for c in df.columns if 'player' in c.lower() or 'name' in c.lower())
# Convert all heights to inches
df['Height_inches'] = df[height_col].apply(parse_height)
reference_in = 6 * 12 + 3 # 6' 3" in inches
# Find all < 6' 3", except taylor kelly
mask = (df['Height_inches'] < reference_in)
answers = df.loc[mask & (df[entity_col].str.lower().str.strip() != 'taylor kelly'), entity_col].tolist()
with open(output_path, 'w', encoding='utf-8') as f:
    for a in answers:
        f.write(str(a) + '\n')
