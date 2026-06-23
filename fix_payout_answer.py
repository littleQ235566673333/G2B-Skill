import pandas as pd

df = pd.read_csv('results/runs/g2b-v8_gpt-4.1_opsv2smoke/train/iter_2/task_nt-8/r0/evolve_nt-8/input.csv')
# The columns are: 'Hand', '1 credit', ..., '5 credits'
# Look for row where Hand is 'Full house', get '4 credits' value
hand_col = 'Hand'
payout_col = '4 credits'
mask = df[hand_col].str.strip().str.lower() == 'full house'
answers = df.loc[mask, payout_col].astype(str).str.strip().tolist()

with open('results/runs/g2b-v8_gpt-4.1_opsv2smoke/train/iter_2/task_nt-8/r0/evolve_nt-8/output.txt', 'w', encoding='utf-8') as f:
    for a in answers:
        f.write(f"{a}\n")
