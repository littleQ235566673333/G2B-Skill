import openpyxl
import re

wb = openpyxl.load_workbook('results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_7/regression_gate/after_fix/core_325-44/input.xlsx')
input_ws = wb['Input']
output_ws = wb['Output']

# Prepare output sheet, clear and add headers
def reset_output(ws):
    ws.delete_rows(1, 10)
    ws.append(['wtype_id', 'name', 'status', 'orgId', 'careType', 'specialtyId', 'contextId'])

def parse_filter(filter_str):
    orgId = re.search(r'"orgId" = "([^"]+)"', filter_str)
    careType = re.search(r'"careType" = "([^"]+)"', filter_str)
    specialtyId = re.search(r'"specialtyId" IN LIST ([\d,]+)', filter_str)
    contextId = re.search(r'"contextId" IN LIST ([\d,]+)', filter_str)
    # Parse lists, strip leading zeros
    specialtyIds = [int(s.lstrip('0')) if s.lstrip('0') != '' else 0 for s in specialtyId.group(1).split(',')] if specialtyId else [None]
    contextIds = [int(c.lstrip('0')) if c.lstrip('0') != '' else 0 for c in contextId.group(1).split(',')] if contextId else [None]
    return {
        'orgId': orgId.group(1) if orgId else None,
        'careType': careType.group(1) if careType else None,
        'specialtyIds': specialtyIds,
        'contextIds': contextIds,
    }

reset_output(output_ws)
row_count = 1  # including header
for row in input_ws.iter_rows(min_row=2, max_row=10, values_only=True):
    wtype_id, name, status, filter_str = row
    if not (wtype_id and name and status and filter_str):
        continue
    parsed = parse_filter(filter_str)
    for specialtyId in parsed['specialtyIds']:
        for contextId in parsed['contextIds']:
            output_ws.append([
                wtype_id, name, status, parsed['orgId'], parsed['careType'], specialtyId, contextId
            ])
            row_count += 1
# Pad with empty rows to reach 10 rows total
while row_count < 10:
    output_ws.append([None]*7)
    row_count += 1
wb.save('results/runs/g2b-skill-spreadsheet_gpt-4.1_v6/train/iter_7/regression_gate/after_fix/core_325-44/output.xlsx')
