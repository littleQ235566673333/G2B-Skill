#!/usr/bin/env bash
# ITSM B v0 cross-seed: 4.1 SS SAPR-A5 seed 0 + R5 mask, 3 reruns
set -e
cd /Users/unique/auto_research/Project/G2B-Skill
mkdir -p logs/itsm
LOG=logs/itsm/itsm_b_v0_eval_4.1_seed0.log
exec > >(tee -a $LOG) 2>&1
echo "=== ITSM B v0 4.1 SS seed 0 cross-seed eval $(date) ==="

RUN_DIR=results/runs/ITSM_B_v0_mask_R5_4.1_seed0
SK="${RUN_DIR}/train/final_skill"

for r in 1 2 3; do
    OUT="${RUN_DIR}/eval_r${r}"
    if [ -f "${OUT}/eval_summary.json" ]; then
        HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
        echo "[$(date '+%H:%M:%S')] r${r} exists hg=${HG}"
        continue
    fi
    echo "[$(date '+%H:%M:%S')] cross-seed eval_r${r} starting"
    .venv/bin/python -m runners.stream_runner eval \
        --bench spreadsheet \
        --skill-dir $SK \
        --output-dir $OUT \
        --model gpt-4.1 \
        --master-seed 0 --heldout-seed 42 \
        --executor-concurrency 4 --grader-concurrency 1
    HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
    echo "[$(date '+%H:%M:%S')] cross-seed r${r} done hg=${HG}"
done

echo ""
echo "=== 4.1 SS seed 0 cross-seed Summary ==="
.venv/bin/python -c "
import json, statistics, os
accs=[]
for r in [1,2,3]:
    p=f'results/runs/ITSM_B_v0_mask_R5_4.1_seed0/eval_r{r}/eval_summary.json'
    if os.path.exists(p):
        accs.append(json.load(open(p))['aggregate']['mean_hard_graded']*100)
print(f'ITSM B v0 4.1 SS seed 0: {accs}')
if len(accs) >= 2:
    print(f'mean={statistics.mean(accs):.2f}, std={statistics.stdev(accs):.2f}')
print(f'baseline SAPR-A5-N2-seed0: 40/47/52 mean 46.33, std 6.03')
"
echo "=== END $(date) ==="
