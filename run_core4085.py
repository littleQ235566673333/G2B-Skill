import pandas as pd
from openpyxl import load_workbook

# Input/output paths
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed2/train/iter_7/regression_gate/before_pass/core_408-5/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed2/train/iter_7/regression_gate/before_pass/core_408-5/output.xlsx'

# 1. Load data
# Read with pandas
try:
    df = pd.read_excel(input_path, dtype=object)
except Exception:
    # If sheet has no header, load without headers
    df = pd.read_excel(input_path, dtype=object, header=None)

# Ensure columns are accessed by label
col_map = {i: c for i, c in enumerate(df.columns)}
col_C = col_map.get(2, 'C')  # 0-based index for C
col_D = col_map.get(3, 'D')
col_E = col_map.get(4, 'E')

# 2. Identify relevant mask
zero_e_mask = df[col_E].fillna(0).astype(float) == 0
br1_mask = df[col_C].astype(str).str.contains('BR1 Sales', na=False)

# 3. Calculate sum in D where E is zero
sum_d = pd.to_numeric(df.loc[zero_e_mask, col_D], errors='coerce').sum()

# 4. Insert sum in D next to the first occurrence of 'BR1 Sales' in C
if br1_mask.any():
    idx = df[br1_mask].index[0]
    df.at[idx, col_D] = sum_d

# 5. Remove all rows where E is zero except for 'BR1 Sales' rows
rows_to_keep = (~zero_e_mask) | br1_mask
filtered_df = df[rows_to_keep].copy()

# 6. Remove completely blank lines
filtered_df = filtered_df.dropna(how='all')

# 7. Write the cleaned dataframe back to output
# Use openpyxl to ensure proper formatting
with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    filtered_df.to_excel(writer, index=False, header=True)
