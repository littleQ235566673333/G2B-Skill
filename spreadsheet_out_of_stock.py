import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_rerun2/eval_45063_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_rerun2/eval_45063_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
s1 = wb['Sheet1']
s2 = wb['Sheet2']

# Build a lookup dict from Sheet2 col A -> col B
lookup = {}
for row in s2.iter_rows(min_row=2, values_only=True):
    if row[0] is not None:
        lookup[row[0]] = row[1]

# For each out-of-stock item in Sheet1 A2:A6, fetch quantity from Sheet2
for i in range(2, 7):
    item = s1[f'A{i}'].value
    qty = lookup.get(item, '')
    s1[f'B{i}'].value = qty

wb.save(output_path)
