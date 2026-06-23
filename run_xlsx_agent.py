import openpyxl

# Load the workbook and the relevant sheets
wb = openpyxl.load_workbook('results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun2/eval_9391_tc1/input.xlsx')
front_ws = wb['Front']
data_ws = wb['Data']

# Read the date from 'Front'!B1
search_date = front_ws['B1'].value

# Prepare lookup for 'Data' sheet in the form {(date, name): value}
data_lookup = {}
for row in data_ws.iter_rows(min_row=2, values_only=True):
    date, _, _, _, agent, value = row[:6]
    data_lookup[(date, agent)] = value
    
# Fill 'Front'!B2:B12 according to logic
for row in range(2, 13):  # Rows 2 to 12 inclusive
    name_cell = f'C{row}'
    output_cell = f'B{row}'
    agent_name = front_ws[name_cell].value
    if search_date is not None and agent_name is not None:
        result = data_lookup.get((search_date, agent_name), None)
    else:
        result = None
    # Write result or blank
    front_ws[output_cell] = result if result is not None else ''

# Save to the new output file
wb.save('results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun2/eval_9391_tc1/output.xlsx')
