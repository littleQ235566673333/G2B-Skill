import pandas as pd

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-pilot-v2/train/iter_2/regression_gate/before_fix/core_57033/input.xlsx'

sheets = pd.read_excel(input_path, sheet_name=None)
df4 = sheets['Sheet4']
md_candidates = [k for k in sheets.keys() if k.lower() == 'md']
md_sheet = md_candidates[0] if md_candidates else list(sheets.keys())[0]
df_md = sheets[md_sheet]

print('Sheet4 columns:', list(df4.columns))
print(f'MD ("{md_sheet}") columns:', list(df_md.columns))
