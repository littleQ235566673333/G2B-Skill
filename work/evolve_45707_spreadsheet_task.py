import openpyxl
from datetime import datetime

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_5/group_45707/r1/evolve_45707/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_5/group_45707/r1/evolve_45707/output.xlsx'

wb = openpyxl.load_workbook(input_path)
sheet = wb.active

# Read column A (dates) and C (values)
dates = [sheet[f'A{i}'].value for i in range(2,70)]
values = [sheet[f'C{i}'].value for i in range(2,70)]

# Convert column A values to datetime.date

date_objs = []
for d in dates:
    if isinstance(d, str):
        try:
            dt = datetime.strptime(d, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            dt = None
    elif isinstance(d, datetime):
        dt = d.date()
    else:
        dt = d
    date_objs.append(dt)

# Prepare column D
def count_ones_in_month_year(month, year):
    count = 0
    for dt, v in zip(date_objs, values):
        if dt is not None and dt.month == month and dt.year == year:
            if v == 1:
                count += 1
    return count

for i in range(2, 70):
    idx = i - 2
    if idx + 1 < len(date_objs) and date_objs[idx] is not None and date_objs[idx + 1] is not None:
        next_day = date_objs[idx + 1]
        if next_day and next_day.day == 1:
            # same month and year as next_day
            count = count_ones_in_month_year(next_day.month, next_day.year)
            sheet[f'D{i}'].value = count
        else:
            sheet[f'D{i}'].value = None
    else:
        sheet[f'D{i}'].value = None

# Retain headers explicitly (already present, but as per instructions)
sheet['A1'].value = sheet['A1'].value
sheet['C1'].value = sheet['C1'].value
sheet['E1'].value = sheet['E1'].value

wb.save(output_path)
