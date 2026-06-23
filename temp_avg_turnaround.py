import openpyxl
import pandas as pd

input_file = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/eval_seed42_rerun1/eval_55708_tc1/input.xlsx'
output_file = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/eval_seed42_rerun1/eval_55708_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_file)
ws = wb['Sheet1']

rows = list(ws.values)
header = rows[0]
data = list(rows[1:])
df = pd.DataFrame(data, columns=header)

# Filter rows: status in ["In Progress", "In Review"] and time >= 6
departments = ['A', 'B', 'C']
statuses = ["In Progress", "In Review"]
df_filtered = df[df['Status'].isin(statuses) & (df['turnaroud time'] >= 6)]

avg_turnaround = df_filtered.groupby('Department')['turnaroud time'].mean()

results = []
for dept in departments:
    value = avg_turnaround.get(dept)
    if pd.isna(value):
        results.append("")
    else:
        results.append(round(value, 2))

# Write to B11:B13
for i, result in enumerate(results):
    ws[f'B{11+i}'] = result

wb.save(output_file)
