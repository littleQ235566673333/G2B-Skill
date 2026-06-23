import pandas as pd
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed0/train/iter_4/regression_gate/after_pass/core_9726/input.xlsx'
df = pd.read_excel(input_path, header=None)
print('Columns:', df.head(10).to_string())
