import pandas as pd

infile = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/train/iter_7/regression_gate/after_fix/core_nt-149/input.csv'
outfile = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/train/iter_7/regression_gate/after_fix/core_nt-149/output.txt'

# Read table
try:
    df = pd.read_csv(infile)
except Exception as e:
    print(f'Failed to read CSV: {e}')
    raise

# Extract the 4-digit year from the 'Date' column
years = pd.to_numeric(df['Date'].astype(str).str.extract(r'(\d{4})', expand=False), errors='coerce')

# Select those built after 1915
mask = years > 1915
answer_rows = df[mask]
names = answer_rows['Name'].dropna().astype(str).tolist()

with open(outfile, 'w', encoding='utf-8') as f:
    for name in names:
        f.write(name + '\n')
