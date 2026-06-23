import openpyxl

# Load workbook and worksheet
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1-PRUNED/eval_seed42/eval_41978_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1-PRUNED/eval_seed42/eval_41978_tc1/output.xlsx'
wb = openpyxl.load_workbook(input_path)
sheet = wb['Cumulative']

year_case_count = {}

# Examine rows 14 to 185
for row in range(14, 186):
    year = sheet[f'G{row}'].value
    status = sheet[f'J{row}'].value
    if year is not None and status is not None:
        if str(status).strip().lower() == 'open':
            # Only count valid year values
            if str(year).isdigit():
                year_case_count[str(year)] = year_case_count.get(str(year), 0) + 1

# Sort years (ascending)
years_sorted = sorted(year_case_count.keys())

# Write counts to I2:I11, retaining original formatting (copy cell style)
for idx, year in enumerate(years_sorted[:10]):
    dest_cell = sheet.cell(row=2+idx, column=9)  # I column
    dest_cell.value = year_case_count[year]

# Save the workbook
wb.save(output_path)
