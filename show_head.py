import pandas as pd
input_xlsx = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed2/train/iter_4/regression_gate/after_pass/core_3413/input.xlsx'
df = pd.read_excel(input_xlsx, engine='openpyxl')
print(df.head(10))
