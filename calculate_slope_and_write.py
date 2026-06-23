# Slope calculation for Q4 averages
q4_averages = [9258, 9024, 10020, 12323]
years = [0, 1, 2, 3]

N = len(years)
sum_x = sum(years)
sum_y = sum(q4_averages)
sum_xx = sum(x*x for x in years)
sum_xy = sum(x*y for x,y in zip(years, q4_averages))

slope = (N * sum_xy - sum_x * sum_y) / (N * sum_xx - sum_x ** 2)

with open('results/runs/skillgrad_gpt-4.1_oqa-gpt41-smoke/train/iter_7/evolve_oqa-111/output.txt', 'w') as f:
    f.write(str(round(slope)))
