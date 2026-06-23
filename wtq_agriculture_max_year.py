import pandas as pd

input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_2/regression_gate/before_pass/core_nt-255/input.csv'
df = pd.read_csv(input_path, header=None)

# The first row is header (years), first column is the descriptive label
header = df.iloc[0, :].tolist()
data = df.iloc[1:, :].reset_index(drop=True)
data.columns = header

# Find the row referring to agricultural volume (not value)
ag_vol_row = data[data[header[0]].str.lower().str.contains('agricultural') & data[header[0]].str.lower().str.contains('volume')].iloc[0]

# Collect years and corresponding values (skip first column, which is label)
years = header[1:]
values = ag_vol_row[1:].tolist()

# Convert to numeric, keeping corresponding years
year_vals = [(y, float(str(v).replace(',', ''))) for y, v in zip(years, values)]
max_val = max(yv[1] for yv in year_vals)
max_years = [y for y, v in year_vals if v == max_val]

output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/train/iter_2/regression_gate/before_pass/core_nt-255/output.txt'
with open(output_path, 'w', encoding='utf-8') as f:
    for year in max_years:
        f.write(year + '\n')
