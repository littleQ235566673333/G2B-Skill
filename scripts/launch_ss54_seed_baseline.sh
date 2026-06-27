#!/usr/bin/env bash
# 5.4 SS seed-only baseline N=3 sequential reruns
set -e
mkdir -p logs/baselines
LOG=logs/baselines/ss54_seed_baseline.log
exec > >(tee -a $LOG) 2>&1
echo "=== 5.4 SS seed baseline N=3 $(date) ==="
RUN_DIR="results/runs/baseline_spreadsheet_gpt54_seed"
mkdir -p $RUN_DIR
for tag in eval eval_rerun1 eval_rerun2; do
    OUT="${RUN_DIR}/${tag}"
    if [ -f "${OUT}/eval_summary.json" ]; then
        echo "[$(date '+%H:%M:%S')] ${tag} already exists, skipping"; continue
    fi
    echo "[$(date '+%H:%M:%S')] launching ${tag}"
    .venv/bin/python -m runners.stream_runner eval \
        --bench spreadsheet \
        --skill-dir seeds \
        --output-dir $OUT \
        --model gpt-5.4 \
        --master-seed 0 --heldout-seed 42 \
        --executor-concurrency 4 --grader-concurrency 1
    if [ -f "${OUT}/eval_summary.json" ]; then
        HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
        echo "[$(date '+%H:%M:%S')] ${tag} DONE: hard_graded=${HG}"
    else
        echo "[$(date '+%H:%M:%S')] ${tag} FAILED (no eval_summary.json)"; exit 1
    fi
done
echo ""
echo "=== Summary ==="
.venv/bin/python -c "
import json, os
accs=[]
for t in ['eval','eval_rerun1','eval_rerun2']:
    p=f'results/runs/baseline_spreadsheet_gpt54_seed/{t}/eval_summary.json'
    if os.path.exists(p):
        d=json.load(open(p))
        accs.append(d['aggregate']['mean_hard_graded']*100)
print('SS 5.4 seed baseline N=3:', [f'{a:.1f}' for a in accs])
if accs:
    import statistics
    print(f'mean={statistics.mean(accs):.2f}, std={statistics.stdev(accs):.2f}, spread={max(accs)-min(accs):.1f}pp')
    print(f'v8 5.4 SS = 69.0 (68/70/69)')
    print(f'v8 - baseline = +{69.0-statistics.mean(accs):.2f}pp')
"
echo "=== END $(date) ==="
