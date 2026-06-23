import pandas as pd

# Read CSV
input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_1/group_nt-260/r2/evolve_nt-260/input.csv'
df = pd.read_csv(input_path)

# Find the illustrator column
illustrator_col = None
for col in df.columns:
    if 'illustrator' in col.lower():
        illustrator_col = col
        break

answer = ''
if illustrator_col:
    # Drop fully empty rows (all-NaNs)
    nonempty = df.dropna(how='all')
    # Find the last valid (non-NaN) value in this column
    last_valid_idx = nonempty[illustrator_col].last_valid_index()
    if last_valid_idx is not None:
        answer = str(nonempty.loc[last_valid_idx, illustrator_col]).strip()

output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_1/group_nt-260/r2/evolve_nt-260/output.txt'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(answer + '\n')
