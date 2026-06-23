import openpyxl

# Load workbook and sheet
input_path = 'results/runs/g2b-v8_gpt-4.1_ss-gpt41/eval_seed1/eval_42198_tc1/input.xlsx'
output_path = 'results/runs/g2b-v8_gpt-4.1_ss-gpt41/eval_seed1/eval_42198_tc1/output.xlsx'
wb = openpyxl.load_workbook(input_path)
sheet = wb.active

for row_idx in range(2, 8):  # for C2 to C7
    # Gather values cumulatively from row 2 to current row
    range_A = [sheet[f'A{i}'].value for i in range(2, row_idx + 1)]
    range_B = [sheet[f'B{i}'].value for i in range(2, row_idx + 1)]
    result = 'Good'
    # Check conditions by priority
    if any(a == 'Potato' and b is False for a, b in zip(range_A, range_B)):
        result = 'Worst'
    elif any(a == 'Tomato' and b is False for a, b in zip(range_A, range_B)):
        result = 'Ignore'
    elif any(a == 'Pickle' and b is False for a, b in zip(range_A, range_B)):
        result = 'Bad'
    sheet[f'C{row_idx}'].value = result

wb.save(output_path)
