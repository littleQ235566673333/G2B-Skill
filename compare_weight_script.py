import pandas as pd
import re
input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/train/iter_4/regression_gate/after_fix/core_nt-378/input.csv'
df = pd.read_csv(input_path)
df.columns = [c.strip() for c in df.columns]
names = ['dexter fields', 'ovie soko']
df['name_clean'] = df['Name'].astype(str).str.strip().str.lower()
players_df = df[df['name_clean'].isin(names)].copy()
def extract_weight(row):
    # First try parsing from Height field, e.g., 6'2",205"
    h = str(row['Height'])
    match = re.search(r',([0-9]{2,3})"', h)
    if match:
        return float(match.group(1))
    return None
players_df['weight_clean'] = players_df.apply(extract_weight, axis=1)
if players_df.shape[0] < 2 or players_df['weight_clean'].isnull().any():
    with open('players_weight_parsing_debug2.txt', 'w', encoding='utf-8') as f:
        f.write(players_df.to_string())
    raise Exception('Could not extract both weights.')
max_weight_idx = players_df['weight_clean'].idxmax()
heavier_name = df.loc[max_weight_idx, 'Name']
with open('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/train/iter_4/regression_gate/after_fix/core_nt-378/output.txt', 'w', encoding='utf-8') as f:
    f.write(str(heavier_name).strip() + '\n')
