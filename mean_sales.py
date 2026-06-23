values = [333.6, 294.3, 1356.6, 231.4, 728.0]
mean = sum(values) / len(values)
with open('results/runs/g2b-v8_gpt-4.1_oqa-gpt41-smoke/train/iter_3/task_oqa-107/r1/evolve_oqa-107/output.txt', 'w') as f:
    f.write(f'{mean:.1f}\n')
