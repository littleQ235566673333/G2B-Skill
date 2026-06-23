import pandas as pd
# Investigate the columns of the spreadsheet to ensure we use correct headers
df = pd.read_excel('results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed2/train/iter_3/regression_gate/after_pass/core_3413/input.xlsx')
print('COLUMNS:', df.columns.tolist())
