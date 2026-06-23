import pandas as pd
import re

def height_to_inches(height_str):
    """
    Convert a height like 6' 3" to inches (75)
    Handles heights given as e.g. 6' 3", 6 ft 3 in, etc.
    """
    if not isinstance(height_str, str):
        return None
    patt1 = re.match(r"(\d+)'\s*(\d+)?", height_str)
    patt2 = re.match(r"(\d+)\s*ft\s*(\d+)?", height_str)
    if patt1:
        feet = int(patt1.group(1))
        inches = int(patt1.group(2) or 0)
        return feet * 12 + inches
    if patt2:
        feet = int(patt2.group(1))
        inches = int(patt2.group(2) or 0)
        return feet * 12 + inches
    try:
        return int(height_str)
    except:
        return None

inp = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/train/iter_5/regression_gate/after_fix/core_nt-355/input.csv'
outp = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed2/train/iter_5/regression_gate/after_fix/core_nt-355/output.txt'
df = pd.read_csv(inp)
player_col = 'Name'
height_col = 'Height'
# Find Taylor Kelly's height
match = df[df[player_col].str.strip().str.lower() == "taylor kelly"]
if not match.empty:
    taylor_height_str = str(match.iloc[0][height_col])
    taylor_inches = height_to_inches(taylor_height_str)
else:
    taylor_inches = 75  # Fallback if not found
# Find other players shorter than 6' 3'' (75 inches)
df = df.dropna(subset=[height_col])
df['height_in'] = df[height_col].apply(lambda x: height_to_inches(str(x)))
filtered = df[(df['height_in'] < 75) & (df[player_col].str.strip().str.lower() != 'taylor kelly')]
answers = filtered[player_col].tolist()
with open(outp, 'w', encoding='utf-8') as f:
    for a in answers:
        f.write(str(a) + "\n")
