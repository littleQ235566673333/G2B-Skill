import openpyxl

# File paths
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/eval_FIXED_r3/eval_57989_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/eval_FIXED_r3/eval_57989_tc1/output.xlsx'

# Load the workbook and get the first sheet
wb = openpyxl.load_workbook(input_path)
ws = wb.active

# Read all data
data = list(ws.values)

# Find header (weekdays), driver names, and data region
days_row = 0
for i, row in enumerate(data):
    if any(str(cell).strip().lower() in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'] for cell in row):
        days_row = i
        break
header = data[days_row]

# Get the driver names and their corresponding row indexes (assuming 1st column is driver name, starting after header)
drivers = []
driver_row_indexes = []
for idx in range(days_row+1, len(data)):
    cell = data[idx][0]
    if cell is not None and str(cell).strip() != '':
        drivers.append(cell)
        driver_row_indexes.append(idx)

# Get the weekday columns
weekday_columns = {}
for col_idx, value in enumerate(header):
    v = str(value).strip().lower()
    if v in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']:
        weekday_columns[v.title()] = col_idx
weekday_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']

# Output range: B25:H43 (row indices 24 to 42, col indices 1 to 7 [0-based])
output_start_row = 24
output_end_row = 43
output_start_col = 1

# Fill synthesis: count non-empty trips for each driver per weekday
for i, driver in enumerate(drivers):
    driver_row = driver_row_indexes[i]
    for j, day in enumerate(weekday_order):
        if day in weekday_columns:
            col = weekday_columns[day]
            val = data[driver_row][col]
            # Count 1 if not empty, otherwise 0
            count = 1 if val is not None and str(val).strip() != '' else 0
            ws.cell(row=output_start_row + i, column=output_start_col + j, value=count)

wb.save(output_path)
