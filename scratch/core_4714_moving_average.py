import openpyxl
import pandas as pd

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_4/regression_gate/before_fix/core_4714/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_4/regression_gate/before_fix/core_4714/output.xlsx'

cols = ['Emp Code', 'Month (YYYYMM)', 'Month', 'Hours']
df = pd.read_excel(input_path, usecols=cols)

if not pd.api.types.is_datetime64_any_dtype(df['Month']):
    df['Month'] = pd.to_datetime(df['Month'], errors='coerce')

output = []

num_rows = df.shape[0]

for idx in range(1, min(25, num_rows)):
    row = df.iloc[idx]
    employee = row['Emp Code']
    month = row['Month']
    if pd.isnull(employee) or pd.isnull(month):
        output.append('n/a')
        continue
    emp_rows = df[(df['Emp Code'] == employee)]
    emp_rows_time = emp_rows[emp_rows['Month'] <= month].sort_values('Month', ascending=False)
    if emp_rows_time.shape[0] < 4:
        output.append('n/a')
        continue
    last_four = emp_rows_time.head(4)
    avg = last_four['Hours'].mean()
    if avg == int(avg):
        avg_out = str(int(avg))
    else:
        avg_out = f"{avg:.2f}".rstrip('0').rstrip('.')
    output.append(avg_out)

wb = openpyxl.load_workbook(input_path)
ws = wb.active
for i, val in enumerate(output, start=2):
    ws[f'E{i}'] = val
wb.save(output_path)
