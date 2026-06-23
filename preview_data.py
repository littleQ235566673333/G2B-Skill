import pandas as pd
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed1/train/iter_1/group_387-16/r0/evolve_387-16/input.xlsx'
df = pd.read_excel(input_path, sheet_name='Sheet1', header=1)
with pd.option_context('display.max_columns', 20, 'display.width', 1000):
    print(df.head(20))
    print('COLUMNS:', df.columns.tolist())
    print('Value Unique Entries:', df['Value'].unique())
    if 'Unnamed: 2' in df.columns:
        print('Unnamed: 2:', df['Unnamed: 2'].tolist())
