import openpyxl

def preview_excel(file_path, max_rows=30, max_cols=10):
    wb = openpyxl.load_workbook(file_path)
    ws = wb.active
    for row in ws.iter_rows(min_row=1, max_row=max_rows, max_col=max_cols, values_only=True):
        print(row)

preview_excel('results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_3/regression_gate/before_pass/core_18935/input.xlsx')
