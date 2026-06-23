import pandas as pd
from openpyxl import load_workbook

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-v2-smoke4/train/iter_3/group_45707/r2/evolve_45707/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-v2-smoke4/train/iter_3/group_45707/r2/evolve_45707/output.xlsx'

# Read spreadsheet (preserve all columns)
df = pd.read_excel(input_path)

dates = pd.to_datetime(df.iloc[:, 0], errors='coerce')
month_year_tuples = list(zip(dates.dt.year, dates.dt.month))
counts_cache = {}

# Ensure there are at least 4 columns for D
if df.shape[1] < 4:
    df.insert(3, 'D', None)

for idx in range(len(df)-1):
    next_date = dates.iloc[idx+1]
    if pd.notna(next_date) and next_date.day == 1:
        myear = (next_date.year, next_date.month)
        if myear not in counts_cache:
            mask = [(y, m) == myear for (y, m) in month_year_tuples]
            count_ones = ((df.iloc[:, 2].values == 1) & mask).sum()
            counts_cache[myear] = count_ones
        df.iloc[idx, 3] = counts_cache[myear]
    else:
        df.iloc[idx, 3] = None
# Set the last row's D to empty
if df.shape[0] > 1:
    df.iloc[len(df)-1, 3] = None

# Write to the output file, keep all headers
with pd.ExcelWriter(output_path, engine='openpyxl', mode='w') as writer:
    df.to_excel(writer, index=False, header=True)
