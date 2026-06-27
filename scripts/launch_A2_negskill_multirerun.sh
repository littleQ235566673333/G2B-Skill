#!/usr/bin/env bash
set -e
cd /Users/unique/auto_research/Project/G2B-Skill
LOG=logs/itsm/A2_negskill_multirerun.log
exec > >(tee -a $LOG) 2>&1
echo "=== A2: NEGSKILL multi-rerun $(date) ==="
RUN_DIR=results/runs/NEGSKILL_test
SK="${RUN_DIR}/train/final_skill"

for r in 2 3; do
    OUT="${RUN_DIR}/eval_r${r}"
    if [ -f "${OUT}/eval_summary.json" ]; then
        HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
        echo "[$(date '+%H:%M:%S')] NEGSKILL r${r} exists hg=${HG}"
        continue
    fi
    echo "[$(date '+%H:%M:%S')] NEGSKILL r${r} starting"
    .venv/bin/python -m runners.stream_runner eval \
        --bench spreadsheet --skill-dir $SK --output-dir $OUT \
        --model gpt-4.1 --master-seed 0 --heldout-seed 42 \
        --executor-concurrency 4 --grader-concurrency 1
    HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
    echo "[$(date '+%H:%M:%S')] r${r} done hg=${HG}"
done

echo ""
echo "=== NEGSKILL N=3 summary ==="
.venv/bin/python -c "
import json, statistics, os
accs=[]
for r in [1,2,3]:
    p=f'results/runs/NEGSKILL_test/eval_r{r}/eval_summary.json'
    if os.path.exists(p):
        accs.append(json.load(open(p))['aggregate']['mean_hard_graded']*100)
print(f'NEGSKILL N=3: {accs}')
if len(accs) >= 2:
    print(f'mean = {statistics.mean(accs):.2f}, std = {statistics.stdev(accs):.2f}')
print(f'baseline SAPR-A5: 47/46/44 mean 45.67')
print(f'ITSM B v0:        54/51/48 mean 51.0')
print(f'signal range = NEGSKILL → baseline → ITSM = {min(accs):.1f} → 45.67 → 51.0')
"
echo "=== END $(date) ==="
