#!/usr/bin/env bash
set -e
cd /Users/unique/auto_research/Project/G2B-Skill
mkdir -p logs/itsm
LOG=logs/itsm/itsm_b_v1_R5_R4.log
exec > >(tee -a $LOG) 2>&1
echo "=== ITSM B v1 R5+R4 mask 4.1 SS $(date) ==="

RUN_DIR=results/runs/ITSM_B_v1_mask_R5_R4
SK="${RUN_DIR}/train/final_skill"

for r in 1 2 3; do
    OUT="${RUN_DIR}/eval_r${r}"
    if [ -f "${OUT}/eval_summary.json" ]; then
        HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
        echo "[$(date '+%H:%M:%S')] r${r} exists hg=${HG}"
        continue
    fi
    echo "[$(date '+%H:%M:%S')] R5+R4 mask eval_r${r} starting"
    .venv/bin/python -m runners.stream_runner eval \
        --bench spreadsheet \
        --skill-dir $SK \
        --output-dir $OUT \
        --model gpt-4.1 \
        --master-seed 0 --heldout-seed 42 \
        --executor-concurrency 4 --grader-concurrency 1
    HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
    echo "[$(date '+%H:%M:%S')] r${r} done hg=${HG}"
done

echo ""
echo "=== R5+R4 mask Summary ==="
.venv/bin/python -c "
import json, statistics, os
accs=[]
for r in [1,2,3]:
    p=f'results/runs/ITSM_B_v1_mask_R5_R4/eval_r{r}/eval_summary.json'
    if os.path.exists(p):
        accs.append(json.load(open(p))['aggregate']['mean_hard_graded']*100)
print(f'R5+R4 mask 4.1 SS: {accs}')
if len(accs) >= 2: print(f'mean={statistics.mean(accs):.2f}, std={statistics.stdev(accs):.2f}')
print(f'comparison candidates:')
print(f'  SAPR-A5 baseline: mean 45.67')
print(f'  ITSM B v0 R5 only r1: 54')
print(f'  R5+R2 r1 (in flight): 45 early')
"
echo "=== END $(date) ==="
