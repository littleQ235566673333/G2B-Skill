import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/eval/eval_38969_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/eval/eval_38969_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
sheet = wb.active

def is_error(value):
    # Check for Excel error types as strings
    if value is None:
        return False
    error_strings = ['#DIV/0!', '#N/A', '#NAME?', '#NULL!', '#NUM!', '#REF!', '#VALUE!', 'error', 'Error', 'ERROR']
    return str(value).strip() in error_strings

for row in range(2, 21):
    s_val = sheet[f'S{row}'].value
    u_val = sheet[f'U{row}'].value
    if is_error(s_val):
        sheet[f'R{row}'].value = 'Upload'
    else:
        try:
            diff = float(u_val)
        except (TypeError, ValueError):
            sheet[f'R{row}'].value = ''
            continue
        if -1 <= diff <= 1:
            sheet[f'R{row}'].value = 'Do not Upload'
        elif diff > 1:
            sheet[f'R{row}'].value = 'to Check'
        else:
            sheet[f'R{row}'].value = ''

wb.save(output_path)
