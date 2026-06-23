import openpyxl

input_path = "results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1-PRUNED/eval_seed42/eval_13284_tc1/input.xlsx"
output_path = "results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1-PRUNED/eval_seed42/eval_13284_tc1/output.xlsx"

wb = openpyxl.load_workbook(input_path)
base_ws = wb['Base']
streets_ws = wb['Streets']

# Load 'Streets' table (skip header, assume B:C:D:F are 2: end rows)
streets_data = []
for row in streets_ws.iter_rows(min_row=2, values_only=True):
    street_name = row[1]  # 'Streets'!B
    min_val = row[2]      # 'Streets'!C
    max_val = row[3]      # 'Streets'!D
    name_val = row[5]     # 'Streets'!F
    # Both min_val and max_val must be populated
    if street_name is not None and min_val is not None and max_val is not None:
        streets_data.append((street_name, min_val, max_val, name_val))

# Process 'Base'!E2:E26:
for row in range(2, 27):
    base_c = base_ws[f'C{row}'].value  # Street name to match
    base_d = base_ws[f'D{row}'].value  # The number to check range
    result = ''
    if base_c is not None and base_d is not None:
        for s_name, s_min, s_max, s_f in streets_data:
            # Check match and inclusion
            try:
                # Convert to float/int for numeric comparison if possible
                num_val = float(base_d)
                num_min = float(s_min)
                num_max = float(s_max)
            except:
                continue
            if base_c == s_name and num_min <= num_val <= num_max:
                result = s_f if s_f is not None else ''
                break
    base_ws[f'E{row}'] = result

wb.save(output_path)
