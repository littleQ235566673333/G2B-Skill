# Read first 20 rows from the CSV, count most commonly played opponent.
import pandas as pd
from collections import Counter

input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_v6/train/iter_7/regression_gate/before_pass/core_nt-215/input.csv'
output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_v6/train/iter_7/regression_gate/before_pass/core_nt-215/output.txt'

# Read first 20 games
n_games = 20

df = pd.read_csv(input_path)

# Select first n_games
games = df.iloc[:n_games]
# 'Opponent' column
opponents = games['Opponent']

# Count appearances
counts = Counter(opponents)
# Find most common
max_count = max(counts.values())
most_common = [team for team, count in counts.items() if count == max_count]

# Write each most played team to a line
with open(output_path, 'w') as f:
    for team in most_common:
        f.write(f"{team}\n")
