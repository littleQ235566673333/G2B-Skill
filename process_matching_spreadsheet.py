import openpyxl

input_path = "results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/eval_seed42_rerun2/eval_13284_tc1/input.xlsx"
output_path = "results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/eval_seed42_rerun2/eval_13284_tc1/output.xlsx"

# Load workbook and sheets
wb = openpyxl.load_workbook(input_path)
base_ws = wb["Base"]
streets_ws = wb["Streets"]

# Read all Streets rows into a list of dicts (header at row 1)
streets_data = []
for row in streets_ws.iter_rows(min_row=2, values_only=True):
    # Ensure columns of interest: B (1), C (2), D (3), F (5) (0-indexed)
    b, c, d, f = row[1], row[2], row[3], row[5]
    # Both min/max must be present
    if b is not None and c is not None and d is not None:
        streets_data.append({
            'name': f, # column F
            'match': b, # column B
            'min': c, # column C
            'max': d # column D
        })

# For each row in Base!E2:E26
for i in range(2, 27):
    base_c = base_ws[f'C{i}'].value
    base_d = base_ws[f'D{i}'].value
    result = ""
    if base_c is not None and base_d is not None:
        # Find first street that matches conditions
        for street in streets_data:
            # Condition 1: exact match on Base!C vs Streets!B
            if base_c == street['match']:
                try:
                    val = float(base_d)
                    minv = float(street['min'])
                    maxv = float(street['max'])
                    if minv <= val <= maxv:
                        result = street['name'] if street['name'] is not None else ""
                        break
                except (ValueError, TypeError):
                    continue
    base_ws[f'E{i}'] = result

# Save to output
wb.save(output_path)
