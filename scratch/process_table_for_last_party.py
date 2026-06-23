import pandas as pd
# Read the CSV file
input_path = 'results/runs/g2b-skill-wtq_gpt-4.1_v6/train/iter_9/regression_gate/after_fix/core_nt-214/input.csv'
table = pd.read_csv(input_path)

# Exclude total/invalid/other/registered rows
exclude = ['Total', 'Invalid/blank votes', 'Registered voters/turnout']
parties = table[~table['Party'].isin(exclude)]
# Remove rows with 'Other parties' (not main parties)
main_parties = parties[~parties['Party'].str.lower().str.contains('other')]

# Convert Votes to integer for sorting
main_parties['Votes_num'] = main_parties['Votes'].apply(lambda v: int(str(v).replace(',', '')) if str(v).replace(',', '').isdigit() else None)
main_parties = main_parties.dropna(subset=['Votes_num'])

# Find the party with the least votes (finished last)
last_party = main_parties.sort_values('Votes_num', ascending=True).iloc[0]['Party']

# Write the answer to the output file
output_path = 'results/runs/g2b-skill-wtq_gpt-4.1_v6/train/iter_9/regression_gate/after_fix/core_nt-214/output.txt'
with open(output_path, 'w') as f:
    f.write(str(last_party)+'\n')
