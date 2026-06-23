import pandas as pd

input_path = 'results/base_trajectories/master_0_heldout_42/wtq/gpt-4.1/nt-367/input.csv'
output_path = 'results/base_trajectories/master_0_heldout_42/wtq/gpt-4.1/nt-367/output.txt'

df = pd.read_csv(input_path)

with open(output_path, 'w', encoding='utf-8') as f:
    f.write(str(len(df)) + '\n')
