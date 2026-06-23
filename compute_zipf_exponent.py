import numpy as np

# Read raw data from file
data = []
with open('unemployment_insurance_state_receipts_2020.txt') as f:
    for line in f:
        fields = line.strip().split()
        try:
            amt = int(fields[-1])  # always last column
            data.append(amt)
        except Exception:
            pass  # skip any malformed line

# Sort descending
amounts = sorted(data, reverse=True)
ranks = np.arange(1, len(amounts)+1)
log_ranks = np.log(ranks)
log_amounts = np.log(amounts)

from scipy.stats import linregress
slope, intercept, r_value, p_value, std_err = linregress(log_ranks, log_amounts)
zipf_exponent = -slope
rounded_exponent = round(zipf_exponent, 3)

with open('results/runs/g2b-v8_gpt-4.1_oqa-gpt41-smoke/eval_seed0/eval_oqa-25_tc1/output.txt', 'w') as f:
    f.write(str(rounded_exponent) + '\n')

# Confirm output
with open('results/runs/g2b-v8_gpt-4.1_oqa-gpt41-smoke/eval_seed0/eval_oqa-25_tc1/output.txt') as f:
    assert f.read().strip() != '', "output.txt is empty—must always write a candidate answer."
