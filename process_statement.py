import openpyxl

def process_statement(input_path, output_path):
    wb = openpyxl.load_workbook(input_path)
    ws = wb['Statement']
    # Find the first row where column A is 'Invoice No.'
    rows_to_delete = 0
    for i, row in enumerate(ws.iter_rows(min_row=1, max_col=1, values_only=True), 1):
        if row[0] == 'Invoice No.':
            rows_to_delete = i - 1
            break
    if rows_to_delete > 0:
        ws.delete_rows(1, rows_to_delete)
    wb.save(output_path)

process_statement(
    'results/runs/g2b-v8_gpt-4.1_ss-gpt41/eval_seed0/eval_168-17_tc1/input.xlsx',
    'results/runs/g2b-v8_gpt-4.1_ss-gpt41/eval_seed0/eval_168-17_tc1/output.xlsx'
)
