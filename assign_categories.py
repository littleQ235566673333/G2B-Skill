import openpyxl

input_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/eval_seed42/eval_524-31_tc1/input.xlsx'
output_path = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-ss41-seed1/eval_seed42/eval_524-31_tc1/output.xlsx'
wb = openpyxl.load_workbook(input_path)
sheet = wb['Exp-DB']

# Dictionary mapping shortened description to category
category_dict = {
    'amazon': 'Shopping',
    'Auto': 'Transport',
    'Check': 'Banking',
    'dining out': 'Food & Drink',
    'AMZN MKTP': 'Shopping',
    # Add other mappings as needed
}

for i in range(1, 54):
    desc = sheet[f'B{i}'].value
    cat = category_dict.get(desc, 'Uncategorized')
    sheet[f'E{i}'].value = cat

wb.save(output_path)