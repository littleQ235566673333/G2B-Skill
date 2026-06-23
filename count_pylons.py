# Parse the CSV table and count the pylons. Some rows mention multiple pylons in Remarks.
import pandas as pd
import re

df = pd.read_csv('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/train/iter_2/group_nt-53/r1/evolve_nt-53/input.csv')

total_pylons = 0
for _, row in df.iterrows():
    remarks = str(row['Remarks']).lower()
    # Try to spot an explicit count
    match = re.search(r'(\d+) pylon', remarks)
    if match:
        total_pylons += int(match.group(1))
    elif 'pylon' in remarks:
        total_pylons += 1
    else:
        # If no clue in Remarks, check if the 'Name' refers to an explicit pylon
        if 'pylon' in str(row['Name']).lower():
            total_pylons += 1
# Write answer
with open('results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/train/iter_2/group_nt-53/r1/evolve_nt-53/output.txt', 'w', encoding='utf-8') as f:
    f.write(f"{total_pylons}\n")
