import openpyxl
import pandas as pd

def process_emp_to_expected(input_path, output_path):
    wb = openpyxl.load_workbook(input_path)
    emp_ws = wb['Emp']
    lookup_ws = wb['Lookup']

    emp_data = list(emp_ws.values)
    lookup_data = list(lookup_ws.values)

    emp_df = pd.DataFrame(emp_data[1:], columns=emp_data[0])
    lookup_df = pd.DataFrame(lookup_data[1:], columns=lookup_data[0])

    output = []
    # Detect variable columns from Emp matching those in lookup or all beyond basic info
    variable_cols = ['Comp1', '2_comp', 'dept1', 'avg sal', 'hike', 'performance']
    for _, row in emp_df.iterrows():
        for var in variable_cols:
            cat_row = lookup_df[lookup_df['Variable'] == var]
            category = 'Survey'
            if not cat_row.empty:
                subcat = cat_row['Subcategory'].values[0]
            else:
                subcat = (
                    'Country' if var in ['Comp1', 'hike'] else
                    'CONTINENT' if var == '2_comp' else
                    'STATE' if var == 'dept1' else
                    'DISTRICT' if var == 'avg sal' else
                    'HEADQTR')
            output.append([
                row['seqno'], row['Empno'], row['ename'], row['Jobid'],
                var, category, subcat, row[var]
            ])

    out_df = pd.DataFrame(output, columns=[
        'seqno','Empno','ename','Jobid','Variable','Category','Subcategory','Value'])

    # Write to excel, starting from A2 on 'Expected'
    with pd.ExcelWriter(output_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
        out_df.to_excel(writer, sheet_name='Expected', startrow=1, header=False, index=False)

if __name__ == '__main__':
    process_emp_to_expected(
        'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/train/iter_3/evolve_547-43/input.xlsx',
        'results/runs/skillgrad_gpt-4.1_SG-FIXU-SEED-N3-seed0/train/iter_3/evolve_547-43/output.xlsx'
    )
