import pandas as pd
import numpy as np
import csv
input_path = 'results/runs/g2b-v8_gpt-4.1_wtq-gpt41-fix/eval_seed0/eval_nt-216_tc1/input.csv'
# Read lines with csv.reader, pad/truncate each row to header length.
with open(input_path, 'r', encoding='utf-8') as f:
    data = list(csv.reader(f))
header = data[0]
rows = []
for row in data[1:]:
    if len(row) < len(header):
        row = row + [None]*(len(header)-len(row))
    if len(row) > len(header):
        row = row[:len(header)]
    rows.append(row)
df = pd.DataFrame(rows, columns=header)
us_chart_col = next(col for col in df.columns if 'us' in col.lower())
track_col = next(col for col in df.columns if any(x in col.lower() for x in ['song', 'track', 'title']))
def extract_rank(val):
    try:
        return int(str(val).strip())
    except:
        return np.nan
us_ranks = df[us_chart_col].apply(extract_rank)
min_rank = us_ranks.min()
top_track_row = df[us_ranks == min_rank].iloc[0]
answer = top_track_row[track_col]
output_path = 'results/runs/g2b-v8_gpt-4.1_wtq-gpt41-fix/eval_seed0/eval_nt-216_tc1/output.txt'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(str(answer).replace('"', '') + '\n')
