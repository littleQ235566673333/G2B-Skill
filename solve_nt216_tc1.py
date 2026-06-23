import pandas as pd
import csv
import re

def fix_row_fields(row):
    # Merge split title fields for problematic rows
    # Most valid rows have 5 fields: Year, Song, US, CAN, Album
    # If more, merge title fields between year and US chart
    if len(row) == 5:
        return row
    if len(row) > 5:
        # The title might be erroneously split, e.g.
        # ['1975', '\One', ' Two', ' Three (Never...', '88', '—', 'singles only']
        # Join fields between first and last two
        return [row[0], ''.join(row[1:-3]), row[-3], row[-2], row[-1]]
    return row

columns = ['Year', 'Song', 'Chart Positions US Country', 'Chart Positions CAN Country', 'Album']
data = []
with open('results/runs/skillgrad_gpt-4.1_wtq-gpt41/eval_seed2/eval_nt-216_tc1/input.csv', encoding='utf-8') as f:
    for _ in range(3):
        next(f)
    reader = csv.reader(f)
    for row in reader:
        fixed = fix_row_fields([item.strip('"') for item in row])
        data.append(fixed)
df = pd.DataFrame(data, columns=columns)
df['Song'] = df['Song'].apply(lambda s: re.sub(r'^\\', '', s).replace('\\"', '"').replace('"', '').strip())
# Remove rows where US chart is missing or not numeric
uspos = df['Chart Positions US Country'].str.strip()
mask = uspos.str.isdigit()
df_valid = df[mask].copy()
df_valid['Chart Positions US Country'] = df_valid['Chart Positions US Country'].astype(int)
# Now, find the song with smallest US chart position (top of the chart -> #1)
top_idx = df_valid['Chart Positions US Country'].idxmin()
top_song = df_valid.loc[top_idx, 'Song']
# Output the answer
with open('results/runs/skillgrad_gpt-4.1_wtq-gpt41/eval_seed2/eval_nt-216_tc1/output.txt', 'w', encoding='utf-8') as f:
    f.write(f'{top_song}\n')
print('Answer written:', top_song)
