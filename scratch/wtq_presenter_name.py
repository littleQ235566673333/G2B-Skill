import pandas as pd

df = pd.read_csv('results/base_trajectories/master_0_heldout_42/wtq/gpt-4.1/nt-342/input.csv')

# Try to find the relevant column for the name of the presenter
possible_cols = [col for col in df.columns if 'presenter' in col.lower() or 'name' in col.lower()]
col_to_use = possible_cols[0] if possible_cols else df.columns[0]

presenter_name = str(df.loc[0, col_to_use]).strip()

with open('results/base_trajectories/master_0_heldout_42/wtq/gpt-4.1/nt-342/output.txt', 'w', encoding='utf-8') as f:
    f.write(presenter_name + '\n')
