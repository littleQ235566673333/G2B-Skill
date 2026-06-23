import pandas as pd

df = pd.read_csv('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_2/group_nt-323/r2/evolve_nt-323/input.csv')
# Normalize column names
cols = [c.strip().lower() for c in df.columns]
df.columns = cols

# Identify rows matching Kevin Grimes, unc, and defender
mask_name = df['player'].str.strip().str.lower() == 'kevin grimes'
mask_team = df['team'].str.strip().str.lower().str.contains('unc')
mask_position = df['position'].str.strip().str.lower() == 'defender'
mask = mask_name & mask_team & mask_position
selected = df.loc[mask]

# Get consecutive years
years = selected['year'].dropna().astype(str).str.strip().tolist()
try:
    years = [int(y) for y in years]
except:
    pass
years.sort()

# Find maximal consecutive runs
if len(years) == 0:
    ans = []
elif len(years) == 1:
    ans = [str(years[0])]
else:
    runs = []
    run = [years[0]]
    for y in years[1:]:
        if y == run[-1] + 1:
            run.append(y)
        else:
            runs.append(run)
            run = [y]
    runs.append(run)
    longest = max(runs, key=len)
    ans = [str(y) for y in longest]

with open('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_2/group_nt-323/r2/evolve_nt-323/output.txt', 'w', encoding='utf-8') as f:
    for a in ans:
        f.write(a + '\n')
