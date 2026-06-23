import openpyxl

# Load workbook and sheets
wb = openpyxl.load_workbook('results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r3/eval_395-36_tc1/input.xlsx')
main_ids_sheet = wb['Main unique ID']
getting_sheet = wb['Result what i am getting']
expecting_sheet = wb['Result what i am expecting ']

def get_ids(sheet, col=1):
    # Read all values in the first column (skipping the header row)
    return [row[0] for row in sheet.iter_rows(min_col=col, max_col=col, min_row=2, values_only=True) if row[0] is not None]

main_id_list = get_ids(main_ids_sheet)
getting_id_list = get_ids(getting_sheet)

print('Main unique IDs:', main_id_list)
print('Getting IDs:', getting_id_list)
