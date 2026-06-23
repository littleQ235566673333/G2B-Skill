import openpyxl

def find_supplier(item_number, wb, supplier_sheets):
    # Checks in all supplier sheets for the given item number, returns the first supplier found
    for s in supplier_sheets:
        ws = wb[s]
        # Skip header (assume row 1 is header)
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] == item_number:
                return s  # Sheet name = Supplier name in this structure
    return None

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/eval_seed42_rerun1/eval_55979_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/eval_seed42_rerun1/eval_55979_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
calc_ws = wb['Calc']
item_number = calc_ws['A10'].value
supplier_sheets = ['Supplier_1','Supplier_2','Supplier_3']

supplier = find_supplier(item_number, wb, supplier_sheets)

# Write supplier name (as sheet name, or can map to nicer if needed)
calc_ws['B7'] = supplier
wb.save(output_path)
