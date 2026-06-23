import openpyxl

# Paths
template = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/eval_seed42_rerun1/eval_42515_tc1/input.xlsx'
output = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-v2-ss41-seed2/eval_seed42_rerun1/eval_42515_tc1/output.xlsx'

# Load workbook
twb = openpyxl.load_workbook(template)
ws = twb.active

# The current formula is: SUM(1/((1/B5)*$B$8))
# The issue: $B$8 is fixed, but user wants it to update row-by-row.
# Approach: in F5:F19, replace $B$8 with $B5 (relative to each row number) so as you drag the formula, it picks from B of the same row each time.

# If user wants $B$8 to step with each row: in F5 use $B5, in F6 use $B6, etc.
# Place the appropriate formula in F5:F19

for row in range(5, 20):
    # Construct the dynamic formula: SUM(1/((1/B{row})*$B{row}))
    formula = f"=SUM(1/((1/B{row})*$B{row}))"
    ws[f'F{row}'].value = formula

# Save
    
twb.save(output)
print('Done')
