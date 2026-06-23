import pandas as pd

# Load table
df = pd.read_csv('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/eval_seed42_rerun1/eval_nt-335_tc1/input.csv')

# Normalize the team column for matching
team_col = 'Team'
winner_col = 'Winners'
ref_team = 'Werder Bremen'
# Coerce "Winners" to int

df[winner_col] = pd.to_numeric(df[winner_col], errors='coerce')
ref_wins = df.loc[df[team_col].str.strip().str.lower() == ref_team.lower(), winner_col].iloc[0]

# Find teams with more wins (strictly greater), excluding Werder Bremen itself
out = df.loc[(df[winner_col] > ref_wins) & (df[team_col].str.strip().str.lower() != ref_team.lower()), team_col].dropna().tolist()

with open('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/eval_seed42_rerun1/eval_nt-335_tc1/output.txt', 'w', encoding='utf-8') as f:
    for val in out:
        f.write(str(val)+'\n')
