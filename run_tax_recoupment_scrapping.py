import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r1/eval_36097_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r1/eval_36097_tc1/output.xlsx'

wbook = openpyxl.load_workbook(input_path)
sheet = wbook.active

for row in range(3, 7):
    original_cost = sheet[f'C{row}'].value
    itv = sheet[f'D{row}'].value
    sale_price = sheet[f'E{row}'].value
    profit = sheet[f'F{row}'].value
    loss = sheet[f'G{row}'].value

    # Calculate recoupment/scrapping allowance
    if loss not in (None, 0):
        value = itv + loss
    elif profit is not None and original_cost is not None and profit < original_cost:
        value = profit
    else:
        value = original_cost - itv

    # Preserve formatting from column I
    number_format = sheet[f'I{row}'].number_format
    sheet[f'H{row}'].value = value
    sheet[f'H{row}'].number_format = number_format

wbook.save(output_path)
