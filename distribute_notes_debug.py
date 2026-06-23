import pandas as pd
file_in = 'results/runs/g2b-v8_gpt-4.1_ss-gpt41-fix/train/iter_2/task_3911/r0/evolve_3911/input.xlsx'
df = pd.read_excel(file_in)
print(df.columns)
print(df.head())
