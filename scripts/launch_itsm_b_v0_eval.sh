#!/usr/bin/env bash
# ITSM B v0 eval: masked SKILL.md (R5 removed) on 4.1 SS, 3 reruns
set -e
cd /Users/unique/auto_research/Project/G2B-Skill
mkdir -p logs/itsm
LOG=logs/itsm/itsm_b_v0_eval.log
exec > >(tee -a $LOG) 2>&1
echo "=== ITSM B v0 eval $(date) ==="

RUN_DIR=results/runs/ITSM_B_v0_mask_R5
SK="${RUN_DIR}/train/final_skill"

for r in 1 2 3; do
    OUT="${RUN_DIR}/eval_r${r}"
    if [ -f "${OUT}/eval_summary.json" ]; then
        HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
        echo "[$(date '+%H:%M:%S')] r${r} exists hg=${HG}"
        continue
    fi
    echo "[$(date '+%H:%M:%S')] eval_r${r} on 4.1 SS starting"
    .venv/bin/python -m runners.stream_runner eval \
        --bench spreadsheet \
        --skill-dir $SK \
        --output-dir $OUT \
        --model gpt-4.1 \
        --master-seed 0 --heldout-seed 42 \
        --executor-concurrency 4 --grader-concurrency 1
    HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
    echo "[$(date '+%H:%M:%S')] eval_r${r} done hg=${HG}"
done

echo ""
echo "=== Summary ==="
.venv/bin/python -c "
import json, statistics
accs=[]
for r in [1,2,3]:
    p=f'results/runs/ITSM_B_v0_mask_R5/eval_r{r}/eval_summary.json'
    import os
    if os.path.exists(p):
        accs.append(json.load(open(p))['aggregate']['mean_hard_graded']*100)
print(f'ITSM_B_v0_mask_R5 4.1 SS: {[f\"{a:.1f}\" for a in accs]}')
if len(accs) >= 2:
    print(f'mean = {statistics.mean(accs):.2f}, std = {statistics.stdev(accs):.2f}')
print(f'baseline SAPR-A5-N2-seed1 4.1 SS: 47/46/44 mean 45.67, std 1.53')
print(f'expected improvement: removing anti-correlated R5 should yield +X pp')
"
echo "=== END $(date) ==="
