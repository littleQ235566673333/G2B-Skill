import openpyxl
from datetime import datetime
from collections import defaultdict

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-U-N3-seed0/train/iter_3/group_4714/r3/evolve_4714/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-U-N3-seed0/train/iter_3/group_4714/r3/evolve_4714/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb['Sheet2']

rows = list(ws.iter_rows(min_row=2, max_row=25, max_col=6, values_only=False))

# Prepare data structure
records = []
for row in rows:
    emp_code = row[0].value
    month = row[2].value
    hours = row[3].value
    records.append({'emp_code': emp_code, 'month': month, 'hours': hours, 'row': row})

# Group by employee, sorted by date
emp_hist = defaultdict(list)
for rec in records:
    # Ignore rows where month is not a datetime
    if isinstance(rec['month'], datetime):
        emp_hist[rec['emp_code']].append(rec)

for emp in emp_hist:
    emp_hist[emp].sort(key=lambda x: x['month'])

# Calculate moving average and indicator
for emp, recs in emp_hist.items():
    for idx, rec in enumerate(recs):
        row = rec['row']
        col_e = row[4]
        col_f = row[5]
        if idx < 3:
            col_e.value = 'n/a'
            col_f.value = 'n/a - less that 4 weeks'
        else:
            window = recs[idx-3:idx+1]
            hours_list = [w['hours'] for w in window if isinstance(w['hours'], (int, float))]
            if len(hours_list) < 4:
                col_e.value = 'n/a'
                col_f.value = 'n/a - less that 4 weeks'
            else:
                avg = sum(hours_list) / 4
                # Format average to omit .0 for integers
                if avg == int(avg):
                    avg = int(avg)
                col_e.value = avg
                col_f.value = 'More than 48' if avg > 48 else 'Less that 48'

wb.save(output_path)
print('Done')
