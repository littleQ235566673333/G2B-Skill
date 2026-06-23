import pandas as pd

fn = 'results/runs/skillgrad_gpt-4.1_wtq-gpt41/eval_seed2/eval_nt-194_tc1/output.txt'
df = pd.read_csv('results/runs/skillgrad_gpt-4.1_wtq-gpt41/eval_seed2/eval_nt-194_tc1/input.csv')
target_idx = df[df['Film'].str.strip().str.lower() == 'toy story 3'.lower()].index[0]
# 'Rank' appears to represent descending gross. The row above is previous (higher gross), so idx-1.
ans = None
if target_idx > 0:
    ans = df.iloc[target_idx-1]['Film']
with open(fn, 'w', encoding='utf-8') as f:
    if ans is not None:
        f.write(str(ans)+'\n')
