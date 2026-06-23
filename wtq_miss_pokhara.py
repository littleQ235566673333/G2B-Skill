import pandas as pd

# File paths
input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_7/group_nt-41/r0/evolve_nt-41/input.csv'
output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_7/group_nt-41/r0/evolve_nt-41/output.txt'

# Read table
df = pd.read_csv(input_path)

# Locate any row mentioning "Miss Pokhara"
lookup = 'miss pokhara'
df_search = df.apply(lambda row: row.astype(str).str.lower().str.strip().str.contains(lookup).any(), axis=1)
df_pokhara = df[df_search]

year_col = None
for col in df_pokhara.columns:
    if 'year' in col.lower():
        year_col = col
        break

answer = ''
if year_col and not df_pokhara.empty:
    years = pd.to_numeric(df_pokhara[year_col], errors='coerce')
    years = years.dropna()
    if not years.empty:
        answer = str(int(years.max()))

with open(output_path, 'w', encoding='utf-8') as f:
    f.write(answer + '\n')
