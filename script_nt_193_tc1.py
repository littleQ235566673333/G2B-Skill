import pandas as pd
import re

input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/eval_seed42/eval_nt-193_tc1/input.csv'
output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/eval_seed42/eval_nt-193_tc1/output.txt'

df = pd.read_csv(input_path)
df.columns = [c.lower().strip() for c in df.columns]

def extract_year(date_str):
    if pd.isna(date_str):
        return None
    match = re.search(r'(20\d{2})', str(date_str))
    return match.group(1) if match else None

df['year'] = df['date'].apply(extract_year)
df_2007 = df[df['year'] == '2007']

results = df_2007['result'].astype(str).str.upper().str.strip()
max_streak = 0
curr_streak = 0
for res in results:
    if res.startswith('W'):
        curr_streak += 1
        if curr_streak > max_streak:
            max_streak = curr_streak
    else:
        curr_streak = 0

with open(output_path, 'w', encoding='utf-8') as f:
    f.write(str(max_streak) + '\n')
