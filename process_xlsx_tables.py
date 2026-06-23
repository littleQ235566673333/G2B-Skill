import openpyxl
import pandas as pd
import numpy as np

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/train/iter_1/group_38985/r2/evolve_38985/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/train/iter_1/group_38985/r2/evolve_38985/output.xlsx'
wb = openpyxl.load_workbook(input_path)
ws = wb.active

# Read the file with pandas

df = pd.read_excel(input_path, sheet_name=0, header=None)
mask = df.notna().any(axis=1)
split_idxs = np.where(~mask)[0]
groups = np.split(df, split_idxs)
groups = [g for g in groups if not g.empty]

# First two groups are our tables
df1, df2 = groups[0], groups[1]
df1 = df1[df1.iloc[0].notna()].reset_index(drop=True)
df2 = df2[df2.iloc[0].notna()].reset_index(drop=True)

table1_names = df1.iloc[:, 0].tolist()
table2_dict = {}
for _, row in df2.iterrows():
    name, value = row.iloc[0], row.iloc[1]
    table2_dict.setdefault(name, []).append(value)

name_count = {}
output_vals = []
for name in table1_names:
    idx = name_count.get(name, 0)
    vals = table2_dict.get(name, [])
    val = vals[idx] if idx < len(vals) else None
    output_vals.append(val)
    name_count[name] = idx + 1

# Write output to D8:D11
for i, val in enumerate(output_vals):
    ws.cell(row=8+i, column=4).value = val

wb.save(output_path)
