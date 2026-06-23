import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun1/eval_414-20_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun1/eval_414-20_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb['Sheet1']

first_invoice_row = None
for row in ws.iter_rows(min_row=1, max_col=1):
    cell_value = row[0].value
    if cell_value and isinstance(cell_value, str) and cell_value.strip().lower() == 'invoice no.':
        first_invoice_row = row[0].row
        break

if first_invoice_row and first_invoice_row > 1:
    ws.delete_rows(1, first_invoice_row-1)

wb.save(output_path)
