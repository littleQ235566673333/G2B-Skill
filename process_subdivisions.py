import openpyxl
import pandas as pd

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed1/train/iter_6/group_42930/r2/evolve_42930/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-ss41-N3-seed1/train/iter_6/group_42930/r2/evolve_42930/output.xlsx'

# Load spreadsheet
df = pd.read_excel(input_path)

# Identify subdivision and year columns
sub_col = next((c for c in df.columns if 'sub' in c.lower()), df.columns[0])
year_col = next((c for c in df.columns if 'year' in c.lower()), df.columns[1])

# Assign subdivision numbers based on earliest house built (smallest year for each subdivision)
early = df.groupby(sub_col)[year_col].min().reset_index()
early = early.sort_values(year_col).reset_index(drop=True)
early['sub_num'] = early.index + 1  # Unique ranking
sub_map = dict(zip(early[sub_col], early['sub_num']))

df['sub_num'] = df[sub_col].map(sub_map)

df_sorted = df.sort_values('sub_num')

# Write sub_num to C2:C22
wb = openpyxl.load_workbook(input_path)
ws = wb.active
for i, val in enumerate(df_sorted['sub_num'].iloc[:21], start=2):
    ws.cell(row=i, column=3, value=val)
wb.save(output_path)
