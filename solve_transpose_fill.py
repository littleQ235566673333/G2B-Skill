from openpyxl import load_workbook

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed2-PRUNED/eval_seed42/eval_341-14_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed2-PRUNED/eval_seed42/eval_341-14_tc1/output.xlsx'
wb = load_workbook(input_path)
problem_ws = wb['problem']
result_ws = wb['result']

# Read problem data (all non-empty A,B rows)
problem_data = []
row_idx = 2 # Skip header if present at row 1
while True:
    a = problem_ws[f'A{row_idx}'].value
    b = problem_ws[f'B{row_idx}'].value
    if a is None and b is None:
        break
    problem_data.append((a, b))
    row_idx += 1

# Read result layout labels from result_ws
# We'll preserve the A column (categories), and fill B (numbers) from the dataset
for write_row in range(2, 29): # 2 to 28, corresponding to B2:B28
    category = result_ws[f'A{write_row}'].value
    # Find first matching entry in problem_data where colA==category
    num_value = None
    for a_val, b_val in problem_data:
        if a_val == category:
            num_value = b_val
            break
    result_ws[f'B{write_row}'].value = num_value

wb.save(output_path)
