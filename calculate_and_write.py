import numpy as np

# Data series
american = np.array([1186, 1317, 1439])
grand_total = np.array([3839, 3636, 3981])

# Ratio percentage
total_american = american.sum()
total_total = grand_total.sum()
ratio_percent = round((total_american / total_total) * 100, 1)

# Pearson correlation coefficient
corr = np.corrcoef(american, grand_total)[0, 1]
corr_rounded = round(corr, 3)

# Output as required
with open('results/runs/g2b-v8_gpt-4.1_oqa-gpt41-smoke/train/iter_7/task_oqa-66/r0/evolve_oqa-66/output.txt', 'w') as f:
    f.write(f'[{ratio_percent},{corr_rounded}]\n')
