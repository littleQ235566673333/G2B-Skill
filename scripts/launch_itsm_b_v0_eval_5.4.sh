#!/usr/bin/env bash
# ITSM B v0 5.4 SS eval (3 reruns) — parallel to 4.1 SS
set -e
cd /Users/unique/auto_research/Project/G2B-Skill
mkdir -p logs/itsm
LOG=logs/itsm/itsm_b_v0_eval_5.4.log
exec > >(tee -a $LOG) 2>&1
echo "=== ITSM B v0 5.4 SS eval $(date) ==="

RUN_DIR=results/runs/ITSM_B_v0_mask_R5_5.4
SK="${RUN_DIR}/train/final_skill"

for r in 1 2 3; do
    OUT="${RUN_DIR}/eval_r${r}"
    if [ -f "${OUT}/eval_summary.json" ]; then
        HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
        echo "[$(date '+%H:%M:%S')] r${r} exists hg=${HG}"
        continue
    fi
    echo "[$(date '+%H:%M:%S')] 5.4 eval_r${r} starting"
    .venv/bin/python -m runners.stream_runner eval \
        --bench spreadsheet \
        --skill-dir $SK \
        --output-dir $OUT \
        --model gpt-5.4 \
        --master-seed 0 --heldout-seed 42 \
        --executor-concurrency 3 --grader-concurrency 1
    HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
    echo "[$(date '+%H:%M:%S')] 5.4 eval_r${r} done hg=${HG}"
done

echo ""
echo "=== 5.4 SS Summary ==="
.venv/bin/python -c "
import json, statistics, os
accs=[]
for r in [1,2,3]:
    p=f'results/runs/ITSM_B_v0_mask_R5_5.4/eval_r{r}/eval_summary.json'
    if os.path.exists(p):
        accs.append(json.load(open(p))['aggregate']['mean_hard_graded']*100)
print(f'ITSM_B_v0_mask_R5 5.4 SS: {[f\"{a:.1f}\" for a in accs]}')
if len(accs) >= 2:
    print(f'mean = {statistics.mean(accs):.2f}, std = {statistics.stdev(accs):.2f}')
print(f'baseline SAPR-A5 5.4 SS = 71/68/64 mean 67.67, std 3.51')
print(f'v8 5.4 SS reference = 68/70/69 mean 69.0, std 1.0 (pipeline mismatch)')
"
echo "=== END $(date) ==="
