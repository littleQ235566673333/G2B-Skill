import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42_rerun1/eval_168-17_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42_rerun1/eval_168-17_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb['Statement']

rows = list(ws.iter_rows(values_only=True))

# Find the first row where column A is 'Invoice No.'
first_idx = next((i for i, r in enumerate(rows) if r[0] == 'Invoice No.'), None)
if first_idx is None:
    raise ValueError("'Invoice No.' not found in column A.")

# Delete preceding rows (before the first occurrence)
# Delete first_idx rows. Deleting row 1 repeatedly
for _ in range(first_idx):
    ws.delete_rows(1)

wb.save(output_path)
