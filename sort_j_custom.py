import openpyxl
from collections import OrderedDict

def write_sorted_data(input_path, output_path):
    wb = openpyxl.load_workbook(input_path)
    ws = wb['sheet1']
    data = list(ws.values)

    # Identify starting row (skip header)
    start_idx = None
    for idx, row in enumerate(data):
        if row[0] == 'ITEM' and row[1] == 'NAME':
            start_idx = idx + 1
            break
    if start_idx is None:
        raise Exception('Header row not found')

    # Find end of table (ignore rows following empty rows)
    rows = []
    seen = set()
    for row in data[start_idx:]:
        item, name, ref = row[0], row[1], row[2]
        # Stop if original columns are empty
        if item is None and name is None and ref is None:
            continue
        if name == 'NAME' or item == 'ITEM':  # skip repeated headers
            continue
        if name is None or ref is None or item is None:
            continue
        # Duplicate filter
        key = (name, ref)
        if key in seen:
            continue
        seen.add(key)
        rows.append({'ITEM': item, 'NAME': name, 'REF': ref})

    # Helper list from column J
    helper_col = []
    for d in data[start_idx:]:
        jval = d[9]
        if jval is not None and jval != 'LIST':
            helper_col.append(jval)
    helper_order = OrderedDict((n, 0) for n in helper_col)

    # If helper_col is empty, sort A-Z
    if not helper_col:
        sorted_rows = sorted(rows, key=lambda r: r['NAME'])
    else:
        # Group rows in helper order, then others
        selected = []
        rest = []
        for row in rows:
            n = row['NAME']
            if n in helper_order:
                selected.append(row)
            else:
                rest.append(row)

        # Keep helper list order
        grouped = []
        for h in helper_order:
            for row in selected:
                if row['NAME'] == h:
                    grouped.append(row)
        grouped.extend(rest)
        sorted_rows = grouped

    # Output to columns G/H, H sorted ascending
    output_data = []
    for row in sorted_rows:
        output_data.append([row['NAME'], row['REF']])
    # Only columns G/H
    output_data = output_data[:9]  # F2:H10 is 9 rows
    # sort column H ascending in output
    output_data.sort(key=lambda x: x[1])

    # Write to output file
    ws_out = wb['sheet1']
    # Clear G2:H10
    for i in range(2, 11):
        ws_out[f'G{i}'] = None
        ws_out[f'H{i}'] = None
    for idx, row in enumerate(output_data):
        ws_out[f'G{idx+2}'] = row[0]
        ws_out[f'H{idx+2}'] = row[1]
    wb.save(output_path)

write_sorted_data(
    'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_rerun1/eval_22-47_tc1/input.xlsx',
    'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_rerun1/eval_22-47_tc1/output.xlsx')
