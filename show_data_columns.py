import pandas as pd
# Print column names from Data sheet
file = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed0/eval_seed42/eval_48365_tc1/input.xlsx'
df = pd.read_excel(file, sheet_name='Data')
print(list(df.columns))
