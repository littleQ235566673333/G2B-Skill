import openpyxl
import datetime

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_TIME-A/eval_8942_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed0/eval_seed42_TIME-A/eval_8942_tc1/output.xlsx'

wb = openpyxl.load_workbook(input_path)
overview_ws = wb['Overview']
paydates_ws = wb['Pay Dates']

selected_date = overview_ws['A2'].value
monthly_total = 0
if selected_date:
    # Handle string or date object in A2
    if isinstance(selected_date, datetime.date):
        month = selected_date.month
        year = selected_date.year
    else:
        # Try to parse if it's a string (e.g., '2024-01-29' or 'January 29')
        try:
            dt = None
            # Try ISO format first
            try:
                dt = datetime.datetime.strptime(selected_date, '%Y-%m-%d')
            except:
                pass
            if dt is None:
                # Try 'Month Day'
                dt = datetime.datetime.strptime(selected_date, '%B %d')
            month = dt.month
            year = None  # Can't assume year if not present
        except Exception:
            month = None
            year = None
    if month is not None:
        for row in paydates_ws.iter_rows(min_row=2, values_only=True):
            date_val = row[0]
            amt_val = row[1] if len(row) > 1 else 0
            if isinstance(date_val, (datetime.date, datetime.datetime)):
                if date_val.month == month:
                    monthly_total += amt_val or 0
overview_ws['B5'].value = monthly_total
wb.save(output_path)
