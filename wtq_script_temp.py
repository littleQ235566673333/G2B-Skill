import pandas as pd
# Read input CSV
input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/eval_seed42/eval_nt-368_tc1/input.csv'
df = pd.read_csv(input_path)

# We don't have an 'Athlete' column; assume all rows are for Yelena Slesarenko
# Look for 'Tournament', 'Result', and 'Year'
target_comp = 'world indoor championships'
df_filtered = df[
    (df['Tournament'].str.strip().str.lower() == target_comp)
    & (df['Result'].str.strip().str.lower() == '1st')
]

if not df_filtered.empty:
    df_filtered = df_filtered.copy()
    df_filtered['Year'] = df_filtered['Year'].astype(int)
    answer = df_filtered.sort_values('Year')['Year'].iloc[-1]
else:
    answer = ''

output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/eval_seed42/eval_nt-368_tc1/output.txt'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(str(answer)+'\n')
