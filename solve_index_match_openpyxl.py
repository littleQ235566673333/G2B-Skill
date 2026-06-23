import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/eval_seed42/eval_55468_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/eval_seed42/eval_55468_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
sheet = wb.active

# Get horizontal (column) headers for X axis
cols = [openpyxl.utils.get_column_letter(i) for i in range(3, 27)] # C to Z
col_header_1 = [sheet[f'{col}4'].value for col in cols]
col_header_2 = [sheet[f'{col}3'].value for col in cols]

# Get vertical (row) headers for Y axis
rows = list(range(5, 11)) # 5 to 10
row_header_1 = [sheet[f'A{row}'].value for row in rows]
row_header_2 = [sheet[f'B{row}'].value for row in rows]

# Criteria
horizontal_criteria_1 = sheet['AC4'].value
horizontal_criteria_2 = sheet['AB4'].value
vertical_criteria_1 = sheet['AE4'].value
vertical_criteria_2 = sheet['AD4'].value

# Find matching column index (across C:Z)
col_index = None
for j in range(len(cols)):
    if col_header_1[j] == horizontal_criteria_1 and col_header_2[j] == horizontal_criteria_2:
        col_index = j
        break

# Find matching row index (across rows 5:10)
row_index = None
for i in range(len(rows)):
    if row_header_1[i] == vertical_criteria_1 and row_header_2[i] == vertical_criteria_2:
        row_index = i
        break

result = None
if row_index is not None and col_index is not None:
    # Data starts at C5
    cell = f'{cols[col_index]}{rows[row_index]}'
    result = sheet[cell].value

sheet['AE5'] = result
wb.save(output_path)
