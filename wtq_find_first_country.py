import pandas as pd

df = pd.read_csv('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/train/iter_8/regression_gate/after_fix/core_nt-305/input.csv')

df['earliest_year'] = df['Year(s) delivered'].astype(str).str.extract(r'(\d{4})').astype(int)
df_sorted = df.sort_values(by='earliest_year')
first_country = df_sorted.iloc[0]['Country'].strip()

with open('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/train/iter_8/regression_gate/after_fix/core_nt-305/output.txt', 'w') as f:
    f.write(first_country + '\n')
