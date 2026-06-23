import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42_rerun1/eval_36097_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed1/eval_seed42_rerun1/eval_36097_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
sheet = wb.active

for row in range(3, 7):
    cost = sheet[f'C{row}'].value or 0
    itv = sheet[f'E{row}'].value or 0
    profit = sheet[f'F{row}'].value or 0
    # Rule 1: Sold at loss
    if profit < 0:
        recoupment = itv + abs(profit)
    # Rule 2: Profit less than cost
    elif profit < cost:
        recoupment = profit
    # Rule 3: Otherwise
    else:
        recoupment = cost - itv
    # Copy formatting from column I
    if sheet[f'I{row}'].has_style:
        sheet[f'H{row}'].font = sheet[f'I{row}'].font
        sheet[f'H{row}'].fill = sheet[f'I{row}'].fill
        sheet[f'H{row}'].border = sheet[f'I{row}'].border
        sheet[f'H{row}'].alignment = sheet[f'I{row}'].alignment
        sheet[f'H{row}'].number_format = sheet[f'I{row}'].number_format
    sheet[f'H{row}'].value = recoupment

wb.save(output_path)
print('Recoupment calculation done and formatting copied.')