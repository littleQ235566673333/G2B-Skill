import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_seed2/eval_13284_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_seed2/eval_13284_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
base_ws = wb['Base']
streets_ws = wb['Streets']

# Read all Streets rows into a list of dicts
streets_data = []
for row in streets_ws.iter_rows(min_row=2, values_only=True):
    street = {
        'code': row[1],   # B
        'min': row[2],    # C
        'max': row[3],    # D
        'name': row[5],   # F
    }
    # Only consider rows where min and max are both populated
    if (street['min'] is not None) and (street['max'] is not None):
        streets_data.append(street)

# Process each row of Base E2:E26
for base_row in range(2, 27):
    base_code = base_ws[f'C{base_row}'].value
    base_num = base_ws[f'D{base_row}'].value
    match_name = ''
    if base_code is not None and base_num is not None:
        for street in streets_data:
            if street['code'] == base_code:
                # Ensure base_num is numeric and within range
                try:
                    base_num_float = float(base_num)
                    min_val = float(street['min'])
                    max_val = float(street['max'])
                except (ValueError, TypeError):
                    continue
                if min_val <= base_num_float <= max_val:
                    match_name = street['name'] if street['name'] is not None else ''
                    break
    base_ws[f'E{base_row}'].value = match_name

wb.save(output_path)
