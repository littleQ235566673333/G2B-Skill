import pandas as pd

df = pd.read_csv('results/runs/g2b-skill-wtq_gpt-4.1_v6/train/iter_6/group_nt-178/r0/evolve_nt-178/input.csv')
province_col = df.columns[0]
wine_col = 'Wine'
df[province_col] = df[province_col].str.replace('"','').str.strip()
# Exclude non-numeric wine entries
df_valid = df[df[wine_col].apply(lambda x: str(x).replace('.','',1).isdigit())]
df_valid[wine_col] = df_valid[wine_col].astype(float)
idx = df_valid[wine_col].idxmax()
top_province = df_valid.loc[idx, province_col]
with open('results/runs/g2b-skill-wtq_gpt-4.1_v6/train/iter_6/group_nt-178/r0/evolve_nt-178/output.txt','w') as f:
    f.write(str(top_province)+'\n')
