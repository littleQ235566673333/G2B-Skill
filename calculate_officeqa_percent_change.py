1940_values = [132,129,143,159,154,153,177,200,219,287,376,473]
1953_values = [3632,3501,3789,3891,3746,4056,3890,3519,3787,3647,3540,3465]

sum_1940 = sum(1940_values)
sum_1953 = sum(1953_values)

percent_change = abs(sum_1953 - sum_1940) / sum_1940 * 100
result = round(percent_change, 2)

with open('results/runs/baseline_officeqa_gpt41_seed/eval/eval_oqa-2_tc1/output.txt', 'w') as f:
    f.write(f"{result}%\n")
