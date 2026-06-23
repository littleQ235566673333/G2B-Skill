import pandas as pd

# Load the table
fpath = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/train/iter_4/regression_gate/before_pass/core_nt-294/input.csv'
df = pd.read_csv(fpath)

# Clean up header names
clean = lambda s: s.replace('\n', ' ').replace('\r', ' ').replace('"', '').replace("'", '').strip().lower()
df.columns = [clean(col) for col in df.columns]

team_col = [c for c in df.columns if 'team' in c][0]
points_col = [c for c in df.columns if 'point' in c][0]

# For debugging: print team column values
tcol = df[team_col].astype(str).str.strip().str.lower().tolist()

# Try various lowering/accents
from unidecode import unidecode
match = lambda name: df[team_col].astype(str).apply(lambda x: unidecode(x).lower().strip() == unidecode(name).lower().strip())
dfa = df[match('C.D. Aguila') | match('C.D. Águila')]
dfc = df[match('Chalatenango')]

assert len(dfa) >= 1 and len(dfc) >= 1, f'Missing row: aguila {len(dfa)}, chalatenango {len(dfc)}'

pa = pd.to_numeric(dfa[points_col], errors='coerce').iloc[0]
pc = pd.to_numeric(dfc[points_col], errors='coerce').iloc[0]
diff = abs(int(pa) - int(pc))

out_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed1/train/iter_4/regression_gate/before_pass/core_nt-294/output.txt'
with open(out_path, 'w') as f:
    f.write(str(diff) + '\n')
