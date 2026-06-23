import openpyxl
import pandas as pd

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed2/eval_seed42_rerun1/eval_48983_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-ST-N3-seed2/eval_seed42_rerun1/eval_48983_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
ws = wb.active

df = pd.read_excel(input_path, sheet_name=ws.title, header=None)

# Fixed ranges from debug:
# Categories in row 5 (index 4)
category_row = 4
category_cols = list(range(12, 19)) # M:S
# Brands are in column L (col 11), rows 6-11 (indexes 5-10)
brand_col = 11
brand_rows = list(range(5, 11)) # 6..11

# For each cell in M6:S11, transfer value where:
# - category from row 5, col M:S
# - brand from col L, row 6:11

for r in brand_rows:
    brand = str(df.iloc[r, brand_col]).strip()
    for c in category_cols:
        category = str(df.iloc[category_row, c]).strip()
        # Now, find matching value:
        # The corresponding value for (brand, category) is at the intersection where col header == brand and row header == category
        # Find col with this brand in header row 5
        source_brand_col = None
        for sc in range(df.shape[1]):
            test = str(df.iloc[category_row-1, sc]).strip()
            if test == brand:
                source_brand_col = sc
                break
        # Find row where first col matches category (row header)
        source_category_row = None
        for sr in range(category_row+1, df.shape[0]):
            test = str(df.iloc[sr, 0]).strip()
            if test == category:
                source_category_row = sr
                break
        val = None
        if source_brand_col is not None and source_category_row is not None:
            val = df.iloc[source_category_row, source_brand_col]
        ws.cell(row=r+1, column=c+1).value = val

wb.save(output_path)
