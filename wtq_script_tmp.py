import pandas as pd

df = pd.read_csv('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/eval_seed42/eval_nt-127_tc1/input.csv')
first_row = df.iloc[0]
# Find a column corresponding to "club name" or similar identifiers for football/club lists
answer = None
for col in df.columns:
    col_lower = col.lower()
    if 'club' in col_lower or 'name' in col_lower:
        answer = first_row[col]
        break
if answer is None:
    answer = first_row[df.columns[0]]  # fallback: just emit first column of the first row
with open('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/eval_seed42/eval_nt-127_tc1/output.txt', 'w', encoding='utf-8') as f:
    f.write(str(answer) + '\n')
