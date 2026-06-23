import pandas as pd

# Input and output paths
table_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_2/group_nt-74/r0/evolve_nt-74/input.csv'
output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_2/group_nt-74/r0/evolve_nt-74/output.txt'

df = pd.read_csv(table_path)

# Find the column containing 'driver'
driver_col = next((c for c in df.columns if 'driver' in c.lower()), None)

if driver_col:
    vc = df[driver_col].value_counts()
    maxval = vc.max()
    most_drivers = vc[vc == maxval].index.tolist()
else:
    most_drivers = []  # No matching column found

with open(output_path, "w", encoding="utf-8") as f:
    for x in most_drivers:
        f.write(str(x) + "\n")
