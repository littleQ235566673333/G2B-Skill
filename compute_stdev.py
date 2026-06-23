prices = [99.342280, 99.213485, 101.434007, 99.570169]

mean = sum(prices) / len(prices)
variance = sum((x - mean) ** 2 for x in prices) / len(prices)
stdev = variance ** 0.5
# Round to 6 decimal places
rounded_stdev = round(stdev, 6)

with open('results/runs/skillgrad_gpt-4.1_oqa-gpt41-smoke/train/iter_6/evolve_oqa-39/output.txt', 'w') as f:
    f.write(f"{rounded_stdev}\n")
