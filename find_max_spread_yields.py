import re

# Extracted Table AY-1 (Average Yields) as parsed from the document.
# We'll store the data in a text block (simulate the table row parse from text for each year)
yields_by_year = '''
1960
Jan. 4.08 4.63
Feb. 4.08 4.60
Mar. 4.16 4.71
Apr. 4.19 4.75
May 4.23 4.82
June 4.31 4.91
July 4.38 5.02
Aug. 4.47 5.06
Sept. 4.52 5.14
Oct. 4.57 5.22
Nov. 4.62 5.30
Dec. 4.68 5.37
1961
Jan. 4.68 5.31
Feb. 4.70 5.35
Mar. 4.73 5.38
Apr. 4.76 5.45
May 4.80 5.55
June 4.87 5.63
July 4.94 5.71
Aug. 5.01 5.79
Sept. 5.07 5.83
Oct. 5.13 5.89
Nov. 5.19 5.94
Dec. 5.26 6.00
1962
Jan. 5.32 6.05
Feb. 5.36 6.13
Mar. 5.40 6.24
Apr. 5.45 6.32
May 5.50 6.38
June 5.58 6.53
July 5.64 6.73
Aug. 5.73 6.77
Sept. 5.80 6.83
Oct. 5.87 6.87
Nov. 5.94 6.94
Dec. 6.00 7.02
1963
Jan. 5.87 6.89
Feb. 5.70 6.65
Mar. 5.53 6.50
Apr. 5.37 6.39
May 5.21 6.22
June 5.08 6.09
July 4.96 5.98
Aug. 4.85 5.91
Sept. 4.72 5.83
Oct. 4.64 5.77
Nov. 4.57 5.72
Dec. 4.47 5.62
1964
Jan. 4.45 5.60
Feb. 4.45 5.51
Mar. 4.45 5.45
Apr. 4.52 5.43
May 4.60 5.49
June 4.67 5.57
July 4.74 5.63
Aug. 4.80 5.66
Sept. 4.89 5.70
Oct. 4.95 5.74
Nov. 5.04 5.79
Dec. 5.09 5.81
1965
Jan. 5.14 5.81
Feb. 5.14 5.80
Mar. 5.15 5.81
Apr. 5.16 5.79
May 5.16 5.77
June 5.20 5.78
July 5.24 5.81
Aug. 5.27 5.90
Sept. 5.30 5.97
Oct. 5.33 6.10
Nov. 5.35 6.21
Dec. 5.37 6.27
1966
Jan. 5.52 6.39
Feb. 5.56 6.45
Mar. 5.63 6.57
Apr. 5.70 6.65
May 5.77 6.77
June 5.83 6.90
July 5.88 7.00
Aug. 5.89 7.05
Sept. 5.88 7.10
Oct. 5.91 7.16
Nov. 5.93 7.18
Dec. 5.90 7.19
1967
Jan. 5.83 7.13
Feb. 5.81 7.16
Mar. 5.81 7.16
Apr. 5.85 7.21
May 5.89 7.23
June 5.97 7.24
July 6.06 7.27
Aug. 6.13 7.27
Sept. 6.18 7.28
Oct. 6.21 7.29
Nov. 6.24 7.32
Dec. 6.29 7.37
1968
Jan. 6.34 7.36
Feb. 6.39 7.37
Mar. 6.46 7.41
Apr. 6.53 7.43
May 6.61 7.46
June 6.72 7.51
July 6.82 7.56
Aug. 6.86 7.61
Sept. 6.90 7.65
Oct. 7.03 7.76
Nov. 7.07 7.83
Dec. 7.09 7.83
1969
Jan. 7.07 7.85
Feb. 7.13 7.88
Mar. 7.16 7.91
Apr. 7.20 7.92
May 7.23 7.92
June 7.27 7.92
July 7.29 7.91
Aug. 7.31 7.92
Sept. 7.32 7.92
Oct. 7.38 7.98
Nov. 7.36 8.01
Dec. 7.35 8.02
'''

# Build a lookup for month names to numbers
month_to_num = {
    'Jan.': 1, 'Feb.': 2, 'Mar.': 3, 'Apr.': 4, 'May': 5, 'June': 6,
    'July': 7, 'Aug.': 8, 'Sept.': 9, 'Oct.': 10, 'Nov.': 11, 'Dec.': 12
}

# Parse the text and fill a list of (year, month, t_yield, c_yield) tuples
data = []
current_year = None
for line in yields_by_year.splitlines():
    line = line.strip()
    # Detect year
    year_match = re.match(r'^(19[6-9][0-9])$', line)
    if year_match:
        current_year = int(year_match.group(1))
        continue
    # Extract month and two yields
    # e.g., 'Jan. 4.08 4.63'
    m = re.match(r'^(Jan\.|Feb\.|Mar\.|Apr\.|May|June|July|Aug\.|Sept\.|Oct\.|Nov\.|Dec\.)\s+([\d.]+)\s+([\d.]+)', line)
    if m and current_year:
        month_name = m.group(1)
        t_yield = float(m.group(2))
        c_yield = float(m.group(3))
        month_num = month_to_num[month_name]
        data.append( (current_year, month_num, t_yield, c_yield) )

# Find the max spread (Aa corporate - Treasury)
best = None
max_spread = None
for year, month, t, c in data:
    spread = c - t
    if (max_spread is None) or (spread > max_spread):
        max_spread = spread
        best = (year, month, t, c, spread)

# Compute final value: (month as int)*100 + year
out_val = best[1]*100 + best[0]

with open("results/runs/g2b-v8_gpt-4.1_oqa-gpt41-smoke/eval_seed0/eval_oqa-15_tc1/output.txt", "w") as f:
    f.write(str(out_val)+"\n")
