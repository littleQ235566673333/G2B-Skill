import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42_rerun1/eval_33157_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42_rerun1/eval_33157_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
sheet = wb['Sheet1']

# Mapping of columns for activities
activity_cols = ['B', 'D', 'F', 'H']
activity_headers = [sheet[f'{col}1'].value for col in activity_cols]

for row in range(2, 7):  # Rows 2 to 6
    date_j = sheet[f'J{row}'].value
    found_activity = ''
    for idx, col in enumerate(activity_cols):
        cell_value = sheet[f'{col}{row}'].value
        # Compare cell_value with date_j; If both are dates or strings, equality is sufficient.
        if cell_value == date_j:
            found_activity = activity_headers[idx]
            break
    sheet[f'K{row}'] = found_activity

wb.save(output_path)
