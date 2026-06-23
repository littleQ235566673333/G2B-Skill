import openpyxl

input_path = 'results/runs/g2b-v8_gpt-4.1_ss-gpt41/eval_seed1/eval_486-17_tc1/input.xlsx'
output_path = 'results/runs/g2b-v8_gpt-4.1_ss-gpt41/eval_seed1/eval_486-17_tc1/output.xlsx'

# Open the input workbook and select the sheet
wb = openpyxl.load_workbook(input_path)
ws = wb['Blad1']

for row in range(2, 131):  # B2:B130
    cell = ws[f'B{row}']
    val = cell.value
    if val is not None:
        val_str = str(val).strip()
        if val_str.startswith('0') and len(val_str) == 9:
            # Remove initial '0', then split to yyyy mm dd
            yyyymmdd = val_str[1:]
            yyyy = yyyymmdd[:4]
            mm = yyyymmdd[4:6]
            dd = yyyymmdd[6:]
            reformatted = f'{yyyy} {mm} {dd}'
        else:
            reformatted = ''  # or keep val_str if you prefer
        cell.value = reformatted
    else:
        cell.value = ''

wb.save(output_path)
