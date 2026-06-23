import csv
import pandas as pd

# Read and reconstruct table with proper splitting on inner
rows = []
with open('results/runs/skillgrad_gpt-4.1_wtq-gpt41/eval_seed0/eval_nt-216_tc1/input.csv') as f:
    reader = csv.reader(f)
    lines = list(reader)[3:]  # skip header
for r in lines:
    # Merge if Song split due to commas
    if len(r) > 5:
        # Merge all pieces from col 1 to the 2nd-to-last three for song
        newrow = [r[0], ','.join(r[1:-3]), r[-3], r[-2], r[-1]]
    else:
        newrow = r
    rows.append(newrow)

# Convert to DataFrame
cols = ['Year','Song','Chart Positions US Country','Chart Positions CAN Country','Album']
df = pd.DataFrame(rows, columns=cols)

# Clean up Song field
# Remove leading/trailing quotes and backslashes
df['Song'] = df['Song'].str.lstrip('\\"').str.rstrip('\\"')

# Clean "Chart Positions US Country" (convert to number, ignore non-numeric)
df['Chart Positions US Country Clean'] = pd.to_numeric(df['Chart Positions US Country'], errors='coerce')
# Drop missing
chart_us_clean = df.dropna(subset=['Chart Positions US Country Clean'])

# Smallest chart position = highest hit
top_row = chart_us_clean.loc[chart_us_clean['Chart Positions US Country Clean'].idxmin()]

# Output the literal Song value
with open('results/runs/skillgrad_gpt-4.1_wtq-gpt41/eval_seed0/eval_nt-216_tc1/output.txt', 'w', encoding='utf-8') as out:
    out.write(str(top_row['Song']) + "\n")
