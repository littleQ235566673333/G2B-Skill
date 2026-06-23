import pandas as pd

# Load the CSV
input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_v6/train/iter_5/regression_gate/after_pass/core_nt-215/input.csv'
df = pd.read_csv(input_path)

# Take the first 20 games
first_20 = df.head(20)

# Count occurrences of each opponent
opponent_counts = first_20['Opponent'].value_counts()

# Find the most frequent
most_played = opponent_counts.idxmax()

# Write answer to file
output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_v6/train/iter_5/regression_gate/after_pass/core_nt-215/output.txt'
with open(output_path, 'w') as f:
    f.write(f'{most_played}\n')
