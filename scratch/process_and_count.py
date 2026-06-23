import pandas as pd
input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_v6/train/iter_5/group_nt-19/r2/evolve_nt-19/input.csv'
df = pd.read_csv(input_path)
def get_winner_score(row):
    score_str = row['Score']
    # Score is like '7–1', '1–2', etc. Find winner.
    parts = score_str.replace('–','-').split('-')
    home_score, away_score = int(parts[0]), int(parts[1])
    if home_score > away_score:
        return home_score
    elif away_score > home_score:
        return away_score
    else:
        return None # Tie
winner_scores = df.apply(get_winner_score, axis=1)
count = sum([s is not None and s > 4 for s in winner_scores])
output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_v6/train/iter_5/group_nt-19/r2/evolve_nt-19/output.txt'
with open(output_path, 'w') as f:
    f.write(f'{count}\n')
