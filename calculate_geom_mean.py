import numpy as np

# Monthly expenditures Mar 1942 to Oct 1948 (inclusive)
values = [
    # 1942 (Mar-Dec)
    3515, 3939, 4100, 4810, 5257, 5456, 5921, 6184, 6012, 6926,
    # 1943 (Jan-Dec)
    6728, 6358, 7746, 7300, 7475, 8260, 7499, 7831, 7667, 7619, 7947, 7744,
    # 1944 (Jan-Dec)
    7737, 8012, 10412, 7337, 6879, 8631, 8014, 8208, 7779, 8034, 7811, 8327,
    # 1945 (Jan-Dec)
    8142, 7127, 9034, 7758, 8927, 9540, 8561, 6949, 6372, 5619, 4530, 4962,
    # 1946 (Jan-Dec)
    4811, 3340, 3598, 3750, 3374, 4836, 3287, 2745, 2663, 2860, 2453, 3605,
    # 1947 (Jan-Dec)
    3019, 3731, 3239, 3407, 3284, 4996, 3553, 2962, 2673, 2394, 2113, 3176,
    # 1948 (Jan-Oct)
    2800, 2224, 3086, 2541, 2222, 7018, 3558, 2143, 2869, 2685
]

print(f"Count: {len(values)}")

# Geometric mean
def geom_mean(seq):
    arr = np.array(seq)
    # To avoid log(0) or negative, but all are positive
    logs = np.log(arr)
    return np.exp(logs.mean())

mean = geom_mean(values)
rounded = round(mean, 2)

with open('results/runs/g2b-v8_gpt-4.1_oqa-gpt41-smoke/eval_seed0/eval_oqa-4_tc1/output.txt', 'w') as f:
    f.write(f"{rounded}\n")
