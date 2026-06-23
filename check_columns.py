import pandas as pd
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed0/eval_seed42_rerun1/eval_50768_tc1/input.xlsx'
df = pd.read_excel(input_path)
print(df.columns.tolist())
