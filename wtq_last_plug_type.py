import pandas as pd

input_file = 'results/runs/skillgrad_gpt-4.1_wtq-gpt41/eval_seed0/eval_nt-134_tc1/input.csv'
output_file = 'results/runs/skillgrad_gpt-4.1_wtq-gpt41/eval_seed0/eval_nt-134_tc1/output.txt'

df = pd.read_csv(input_file)
# Map column: 'IEC\nWorld Plugs\nType1' holds the plug type
types = df['IEC\nWorld Plugs\nType1'].dropna().astype(str).str.strip().tolist()
# Exclude blanks or non-data
types_filtered = [t for t in types if t.lower() not in ('', 'nan')]
# Last one in data order
last_type = types_filtered[-1]
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(f'{last_type}\n')
print('LAST IEC WORLD PLUG TYPE:', last_type)
