import openpyxl

input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun2/eval_18645_tc1/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/eval_seed42_rerun2/eval_18645_tc1/output.xlsx'

# Load workbook
wb = openpyxl.load_workbook(input_path)

# 1. Read stage-percent mapping from Data sheet
data_ws = wb['Data']
stage_to_pct = {}
for row in data_ws.iter_rows(min_row=2, values_only=True):
    if row[0] is None or row[1] is None:
        continue
    stage = row[0]
    pct = row[1]
    try:
        # Handle percent-as-string or numeric
        pct_num = float(str(pct).replace('%',''))/100 if '%' in str(pct) else float(pct)
    except:
        continue
    stage_to_pct[stage] = pct_num

# 2. Fill weighted revenue in Opportunities sheet
opp_ws = wb['Opportunities']
for row in range(2, 4):  # G2:G3
    stage = opp_ws[f'E{row}'].value
    revenue = opp_ws[f'F{row}'].value
    pct = stage_to_pct.get(stage, None)
    weighted_revenue = revenue * pct if pct is not None and revenue is not None else None
    opp_ws[f'G{row}'].value = weighted_revenue

# Save output
wb.save(output_path)
