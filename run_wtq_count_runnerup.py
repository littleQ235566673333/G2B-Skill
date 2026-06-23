import pandas as pd

df = pd.read_csv('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/eval_seed42_rerun1/eval_nt-357_tc1/input.csv')
count = (df['Player outcome'].astype(str).str.strip().str.lower() == 'runner-up').sum()
with open('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/eval_seed42_rerun1/eval_nt-357_tc1/output.txt', 'w', encoding='utf-8') as f:
    f.write(str(count) + '\n')
