import pandas as pd

df = pd.read_csv('results/runs/g2b-v8_gpt-4.1_wtq-gpt41/eval_seed1/eval_nt-220_tc1/input.csv')

# Find rows involving Scheider
df_scheider = df[df['Result'].str.contains('Scheider', case=False, na=False)]

# Find the rows where Scheider lost
scheider_losses = df_scheider[df_scheider['Record'].str.lower() == 'loss']

# Extract the Opponent for these rows
opponents = scheider_losses['Opponent'].dropna().unique()

with open('results/runs/g2b-v8_gpt-4.1_wtq-gpt41/eval_seed1/eval_nt-220_tc1/output.txt', 'w') as f:
    for o in opponents:
        f.write(str(o) + '\n')
