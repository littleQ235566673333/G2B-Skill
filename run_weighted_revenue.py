import openpyxl

# Input and output file paths
input_path = 'results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r1/eval_18645_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r1/eval_18645_tc1/output.xlsx'

# Load workbook
wb = openpyxl.load_workbook(input_path)

# Read mapping from Data tab
stage_to_pct = {}
data_ws = wb['Data']
for row in data_ws.iter_rows(min_row=2, max_col=2, values_only=True):
    stage, pct = row
    if stage is None or pct is None:
        continue
    try:
        pct = float(pct)
    except Exception:
        continue
    stage_to_pct[stage] = pct

# Process Opportunities sheet
opp_ws = wb['Opportunities']
for row in range(2, 4):  # G2:G3
    revenue = opp_ws[f'F{row}'].value
    stage = opp_ws[f'E{row}'].value
    pct = stage_to_pct.get(stage, 0)
    try:
        weighted = revenue * pct
    except Exception:
        weighted = None
    opp_ws[f'G{row}'].value = weighted

wb.save(output_path)
