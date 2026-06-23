import openpyxl
from openpyxl.utils import column_index_from_string

def count_increases(sheet, row, start_col_letter, end_col_letter, threshold=0.1):
    start_col = column_index_from_string(start_col_letter)
    end_col = column_index_from_string(end_col_letter)
    values = [sheet.cell(row=row, column=col).value for col in range(start_col, end_col + 1)]
    
    count = 0
    idx = 0
    n = len(values)
    while idx < n:
        ref = values[idx]
        if ref is None:
            break
        for j in range(idx + 1, n):
            val = values[j]
            if val is None:
                break
            if val >= ref * (1 + threshold):
                count += 1
                # Restart from this cell
                idx = j
                break
        else:
            # No further increases found
            break
        idx += 1
    return count

input_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/train/iter_6/evolve_51-12/input.xlsx'
output_path = 'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed2/train/iter_6/evolve_51-12/output.xlsx'
wb = openpyxl.load_workbook(input_path)
sheet = wb['Sheet1']

# Change these to your actual target range, e.g., ('L', 'SHA', 26)
start_col_letter = 'L'
end_col_letter = 'SHA'
target_row = 1  # Change to 26 for your actual data

result = count_increases(sheet, target_row, start_col_letter, end_col_letter)
sheet['B6'] = result
wb.save(output_path)
