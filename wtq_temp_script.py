import pandas as pd

# Load CSV
df = pd.read_csv('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_5/group_nt-8/r3/evolve_nt-8/input.csv')
df.columns = [c.lower().strip() for c in df.columns]

# filter for row where hand is 'full house'
mask = df['hand'].str.lower().str.strip() == 'full house'
# get value in '4 credits' column for this row
answers = df.loc[mask, '4 credits'].dropna().astype(str)

with open('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_5/group_nt-8/r3/evolve_nt-8/output.txt', 'w', encoding='utf-8') as f:
    for a in answers:
        f.write(a + '\n')
