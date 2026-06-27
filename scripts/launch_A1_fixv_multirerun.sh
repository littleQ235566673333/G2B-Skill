#!/usr/bin/env bash
set -e
cd /Users/unique/auto_research/Project/G2B-Skill
mkdir -p logs/itsm
LOG=logs/itsm/A1_fixv_multirerun.log
exec > >(tee -a $LOG) 2>&1
echo "=== A1: FIX-V multi-rerun consolidation $(date) ==="

for seed in 0 1 2; do
    RUN_DIR=results/runs/ITSM_B_v0_mask_R5_FIX-V-seed${seed}
    SK="${RUN_DIR}/train/final_skill"
    [ ! -d "$SK" ] && continue
    for r in 2 3; do
        OUT="${RUN_DIR}/eval_r${r}"
        if [ -f "${OUT}/eval_summary.json" ]; then
            HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
            echo "[$(date '+%H:%M:%S')] seed${seed} r${r} exists hg=${HG}, skip"
            continue
        fi
        echo "[$(date '+%H:%M:%S')] seed${seed} r${r} starting"
        .venv/bin/python -m runners.stream_runner eval \
            --bench spreadsheet --skill-dir $SK --output-dir $OUT \
            --model gpt-4.1 --master-seed 0 --heldout-seed 42 \
            --executor-concurrency 4 --grader-concurrency 1
        HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
        echo "[$(date '+%H:%M:%S')] seed${seed} r${r} done hg=${HG}"
    done
done

# Aggregate
echo ""
echo "=== FIX-V N=3 final summary ==="
.venv/bin/python -c "
import json, statistics, os
for s in [0,1,2]:
    accs=[]
    for r in [1,2,3]:
        p=f'results/runs/ITSM_B_v0_mask_R5_FIX-V-seed{s}/eval_r{r}/eval_summary.json'
        if os.path.exists(p):
            accs.append(json.load(open(p))['aggregate']['mean_hard_graded']*100)
    if len(accs) >= 2:
        print(f'FIX-V seed{s}: {accs} → mean {statistics.mean(accs):.2f}, std {statistics.stdev(accs):.2f}')
    else:
        print(f'FIX-V seed{s}: {accs} (incomplete)')
"
echo "=== END $(date) ==="
