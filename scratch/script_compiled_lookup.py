import openpyxl

# File paths
input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_8/group_55427/r2/evolve_55427/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_8/group_55427/r2/evolve_55427/output.xlsx'

wb = openpyxl.load_workbook(input_path)
urn_lookup_sheet = wb['URN lookup']
compiled_sheet = wb['Compiled and located schools da']

# Build URN to DFES mapping from 'URN lookup' (K: URN, D: DFES)
urn_to_dfes = {}
for r in range(2, 1462):  # 2 to 1461 inclusive
    urn = urn_lookup_sheet[f'K{r}'].value
    dfes = urn_lookup_sheet[f'D{r}'].value
    urn_to_dfes[urn] = dfes

# Perform the lookup for each URN in Compiled and located schools da!L2:L1461
for r in range(2, 1462):  # 2 to 1461 inclusive
    urn = compiled_sheet[f'L{r}'].value
    dfes = urn_to_dfes.get(urn, None)
    compiled_sheet[f'B{r}'].value = dfes

wb.save(output_path)
