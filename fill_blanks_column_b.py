import openpyxl

# Load the workbook and select the active sheet
wb = openpyxl.load_workbook('results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/eval_seed42/eval_1563_tc1/input.xlsx')
sheet = wb.active

last_value = None

for row in range(2, 31):  # B2:B30
    value = sheet[f'A{row}'].value
    if value is not None and str(value).strip() != '':
        last_value = value
        sheet[f'B{row}'].value = value
    else:
        sheet[f'B{row}'].value = last_value

# Save the output
wb.save('results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/eval_seed42/eval_1563_tc1/output.xlsx')
