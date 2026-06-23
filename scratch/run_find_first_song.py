import pandas as pd

df = pd.read_csv('results/runs/g2b-skill-wtq_gpt-4.1_v6/eval/eval_nt-259_tc1/input.csv')
df = df.sort_values('Year', ascending=True)
first_song = df.iloc[0]['Title']
cleaned = str(first_song).replace('"','').replace('\\','').strip()
with open('results/runs/g2b-skill-wtq_gpt-4.1_v6/eval/eval_nt-259_tc1/output.txt', 'w') as f:
    f.write(cleaned + '\n')
