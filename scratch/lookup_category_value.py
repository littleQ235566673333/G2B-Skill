import openpyxl

# File paths
data_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_4/regression_gate/before_pass/core_18935/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_4/regression_gate/before_pass/core_18935/output.xlsx'

# Load workbook
data_wb = openpyxl.load_workbook(data_path)
data_ws = data_wb.active

# --- Data Table: Rows 4–10 ---
# Headers in row 4 (index 3)
data_table_headers = [cell.value for cell in data_ws[4]]

# Category Types
category_types = data_table_headers[2:5]  # 'Category 1', 'Category 2', 'Category 3'

def get_data_table(ws):
    table = []
    for row in ws.iter_rows(min_row=5, max_row=10, values_only=True):
        if row[0] is None:
            continue
        table.append(row)
    return table

data_table = get_data_table(data_ws)

# --- Report Rows: 17–22 ---
for row_num in range(17, 23):
    work = data_ws[f'A{row_num}'].value
    category_type = data_ws[f'B{row_num}'].value
    material = data_ws[f'C{row_num}'].value
    
    # Lookup row in Data Table
    category_value = None
    for data_row in data_table:
        # data_row: (Work, Material, Cat1, Cat2, Cat3, ...)
        if str(data_row[0]) == str(work) and str(data_row[1]) == str(material):
            # Find column index for the category type
            if category_type in category_types:
                col_idx = data_table_headers.index(category_type)
                category_value = data_row[col_idx]
            break
    # Output result
    data_ws[f'D{row_num}'] = category_value

# Save the workbook with the filled values
data_wb.save(output_path)
