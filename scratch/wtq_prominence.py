import pandas as pd

input_path = 'results/base_trajectories/master_0_heldout_42/wtq/gpt-4.1/nt-158/input.csv'
df = pd.read_csv(input_path)
df.columns = [c.strip().strip('"') for c in df.columns]  # Normalize header

# Preview data & columns:
# print(df.head())
# print(df.columns)

# Clean and match Prominence values (extract number portion, no unit)
def get_prom_ft(val):
    if pd.isna(val):
        return None
    s = str(val).split('ft')[0].replace(',', '').strip().replace('"', '')
    try:
        return float(s)
    except Exception:
        return None

prominences = df['Prominence'].apply(get_prom_ft)
mask = prominences > 10000
df_filtered = df[mask]

answers = df_filtered['Mountain Peak'].dropna().astype(str)

output_path = 'results/base_trajectories/master_0_heldout_42/wtq/gpt-4.1/nt-158/output.txt'
with open(output_path, 'w', encoding='utf-8') as f:
    for a in answers:
        f.write(a + '\n')
