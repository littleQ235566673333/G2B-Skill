import pandas as pd

df = pd.read_csv('results/runs/g2b-v8_gpt-4.1_opsv2smoke/train/iter_2/task_nt-25/r2/evolve_nt-25/input.csv')
# Identify column related to year or founded
year_col = [c for c in df.columns if 'year' in c.lower() or 'founded' in c.lower()]
year_col = year_col[0] if year_col else df.columns[0]
# Ensure string and strip extra whitespace
is_1800s = df[year_col].astype(str).str.strip().str.match(r'18\\d{2}$')
count = is_1800s.sum()
with open('results/runs/g2b-v8_gpt-4.1_opsv2smoke/train/iter_2/task_nt-25/r2/evolve_nt-25/output.txt', 'w', encoding='utf-8') as f:
    f.write(str(count)+'\n')
