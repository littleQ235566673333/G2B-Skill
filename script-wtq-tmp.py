import pandas as pd
import re
input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/eval_seed42_rerun1/eval_nt-86_tc1/input.csv'
output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/eval_seed42_rerun1/eval_nt-86_tc1/output.txt'
df = pd.read_csv(input_path)
party_col = 'Name'
mp_col = 'MPs'
def extract_first_number(s):
    if pd.isnull(s):
        return 0
    m = re.match(r'\s*(\d+)', str(s))
    return int(m.group(1)) if m else 0
df['MP_count'] = df[mp_col].apply(extract_first_number)
groups = df.groupby(party_col)['MP_count'].sum()
max_mp = groups.max()
max_party = groups[groups == max_mp].index.tolist()
with open(output_path, 'w', encoding='utf-8') as f:
    for p in max_party:
        f.write(str(p) + '\n')
