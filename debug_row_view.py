import pandas as pd

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed2/eval_seed42_rerun1/eval_48983_tc1/input.xlsx'

df = pd.read_excel(input_path, header=None)
for i in range(4, 11):
    print(f'Row {i+1}:', df.iloc[i,:30].tolist())
