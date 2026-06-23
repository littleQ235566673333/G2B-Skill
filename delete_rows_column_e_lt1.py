import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1-PRUNED/eval_seed42/eval_374-18_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1-PRUNED/eval_seed42/eval_374-18_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb['Sheet1']

# Collect rows to delete, excluding header (row 1)
rows_to_delete = []
for row in ws.iter_rows(min_row=2):
    cell = row[4]  # Column E (5th column)
    val = cell.value
    if val is not None and isinstance(val, (int, float)):
        if val < 1:
            rows_to_delete.append(cell.row)

# Delete rows in reverse order
for r in sorted(rows_to_delete, reverse=True):
    ws.delete_rows(r)

wb.save(output_path)
