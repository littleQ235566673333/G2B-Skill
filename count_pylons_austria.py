import pandas as pd

input_file = 'results/runs/skillgrad_gpt-4.1_wtq-gpt41/train/iter_4/evolve_nt-350/input.csv'
output_file = 'results/runs/skillgrad_gpt-4.1_wtq-gpt41/train/iter_4/evolve_nt-350/output.txt'

df = pd.read_csv(input_file)
# Count pylons (rows) in Austria, case-insensitive
mask = df['Country'].astype(str).str.strip().str.lower() == 'austria'
count = mask.sum()
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(str(count) + '\n')
