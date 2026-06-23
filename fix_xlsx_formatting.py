import openpyxl

def format_end_values(outfile, sheetname, start_data=2, start_col=9, end_col=18):
    wb = openpyxl.load_workbook(outfile)
    ws = wb[sheetname]
    for row in ws.iter_rows(min_row=start_data, min_col=start_col, max_col=end_col):
        for cell in row:
            val = cell.value
            # Clean up blank-like values or zeros
            if val in [None, '\xa0', 0, 0.0, '0', '0.0', '']:
                cell.value = ''
            else:
                # Try formatting as float (handle exceptions by leaving raw value)
                try:
                    num = float(val)
                    if abs(num) < 1e-12:
                        cell.value = ''
                    else:
                        cell.value = f"{num:.2f}"  # No commas
                except Exception:
                    pass  # leave as is
    wb.save(outfile)

if __name__ == "__main__":
    format_end_values(
        'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-Q-smoke16/train/iter_1/group_177-6/r0/evolve_177-6/output.xlsx',
        'combined', start_data=2, start_col=9, end_col=18
    )
