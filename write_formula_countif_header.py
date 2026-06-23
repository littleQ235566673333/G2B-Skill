import openpyxl

input_path = "results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/eval_seed42_rerun1/eval_46897_tc1/input.xlsx"
output_path = "results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/eval_seed42_rerun1/eval_46897_tc1/output.xlsx"

# Load workbook and default sheet
wb = openpyxl.load_workbook(input_path)
ws = wb.active

# The user wants a formula in cell I3 that counts the instances of a specific text or number in a column matching a specified header title
# Let's assume:
# - The header title to match is entered in cell H1
# - The value to count is entered in cell H2
# So our formula will reference these cells dynamically.

# The formula:
# Get the column with the matching header (from row 1), count matching value in H2 starting from row 2 down to the bottom.
# =COUNTIF(INDEX(1:1048576,0,MATCH(H1,1:1,0)),H2)
# But Excel formulas for dynamic column addressing can use INDIRECT as well for broad compatibility.
formula = '=COUNTIF(INDIRECT(ADDRESS(2,MATCH(H1,1:1,0)) & ":" & ADDRESS(1048576,MATCH(H1,1:1,0))), H2)'

ws['I3'] = formula

wb.save(output_path)
