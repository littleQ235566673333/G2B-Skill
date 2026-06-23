import re
from pathlib import Path

def extract_leading_digit_counts(table_txt):
    pattern = re.compile(r'\|([^|]*)')
    lines = table_txt.strip().splitlines()

    # skip header lines (find the first line with numbers)
    # find start and end of table (detect years: 1971, 1972 etc. or months)
    datalines = []
    inside_numeric = False
    for line in lines:
        if re.match(r'\|?\s*20\d\d|19\d\d', line) or re.match(r'\|?\s*19\d\d', line):
            inside_numeric = True
        if inside_numeric:
            if line.strip() == '' or line.startswith('| End of fiscal'):  # break at any next header
                break
            datalines.append(line)

    # At this point, datalines should include the content rows (one line per row, '|' delimited)
    count = 0
    for line in datalines:
        if not line.strip() or line.lstrip().startswith('| ---'):
            continue  # skip blank and separator
        # skip row header portion after splitting
        parts = [x.strip() for x in line.split('|')][1:]  # first after split is empty due to pipe at start
        for cell in parts:
            # remove units marker (like 'r') and commas/spaces
            cell = cell.replace(',', '').replace('r', '').replace('*', '').strip()
            # skip blanks
            if not cell: continue
            # check for a valid number at start
            m = re.match(r'^-?\d+', cell)
            if m and m.group(0):
                norm = m.group(0).lstrip('-')
                # skip total/avg if likely (e.g., lines like 'Total', 'Average', etc.)
                if norm and norm[0] == '1':
                    count += 1
    return count

def count_leading_ones_in_tb41():
    file = Path('results/runs/g2b-v8_gpt-4.1_oqa-gpt41-smoke/eval_seed0/eval_oqa-21_tc1/sources/treasury_bulletin_1980_05.txt')
    txt = file.read_text(encoding='utf-8', errors='replace')
    # Extract Table MS-1 (page 23/pdf 41)
    # Find region: 'Table MS-1. - Currency and Coin in Circulation' ... to next table or 'FEDERAL DEBT' or 'Table FD-1.'
    m = re.search(r'(Table MS-1\. - Currency and Coin in Circulation[\s\S]+?)(?:Table FD-1|May 1980\\n24|\\n24|FEDERAL DEBT)', txt)
    if not m:
        raise ValueError('Could not find Table MS-1 in document.')
    table_txt = m.group(1)

    # Now: count leading '1' numerals
    n_ones = extract_leading_digit_counts(table_txt)
    # Write result
    outpath = Path('results/runs/g2b-v8_gpt-4.1_oqa-gpt41-smoke/eval_seed0/eval_oqa-21_tc1/output.txt')
    outpath.write_text(f'{n_ones}\n', encoding='utf-8')
    # Confirm not empty
    with open(outpath) as f:
        assert f.read().strip(), 'No output written!'

if __name__ == '__main__':
    count_leading_ones_in_tb41()