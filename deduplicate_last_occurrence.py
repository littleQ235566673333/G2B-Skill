import pandas as pd

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed1/train/iter_7/regression_gate/after_fix/core_280-17/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed1/train/iter_7/regression_gate/after_fix/core_280-17/output.xlsx'

# Read Excel file
df = pd.read_excel(input_path, engine='openpyxl')

# Choose the column to deduplicate by (default: first column)
keycol = df.columns[0]

# Remove all but the last occurrence of each unique value in the key column
deduped = df.drop_duplicates(subset=keycol, keep='last')

# Write the result to an output Excel file
deduped.to_excel(output_path, index=False, engine='openpyxl')
