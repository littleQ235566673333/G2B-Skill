import pandas as pd
header = ['Constituency number','Name','Reserved for (SC/ST/None)','District','Number of electorates (2009)']
df = pd.read_csv('temp.csv', header=None, names=header, quotechar='"')
def parse_number(n):
    n = str(n).replace(',', '')
    try:
        return int(n)
    except ValueError:
        return float(n)
df['Number of electorates (2009)'] = df['Number of electorates (2009)'].apply(parse_number)
result = df.groupby('District')['Number of electorates (2009)'].sum()
max_val = result.max()
answer = result[result == max_val].index.tolist()
with open('results/runs/g2b-skill-wtq_gpt-4.1_v6/train/iter_9/group_nt-123/r1/evolve_nt-123/output.txt', 'w') as f:
    for a in answer:
        f.write(f'{a}\n')
