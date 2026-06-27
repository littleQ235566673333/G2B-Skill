#!/usr/bin/env bash
# SAPR-A5 on GPT-5.4 SS, seed 0 — single train + 3 eval reruns
# Bypass launcher's quick-exp-PASS gate (testing effect, not validating pre-reg)
set -e
cd /Users/unique/auto_research/Project/G2B-Skill
mkdir -p logs/sapr_5.4
LOG=logs/sapr_5.4/a5_ss54_seed0.log
exec > >(tee -a $LOG) 2>&1

echo "=== SAPR-A5 on 5.4 SS seed 0 launch $(date) ==="
RUN_DIR="results/runs/g2b-skill-spreadsheet_gpt-5.4_SAPR-A5-SS54-N1-seed0"

# Phase 1: train (8 iter, K=4, n_train=32)
if [ -d "${RUN_DIR}/train/final_skill" ]; then
    echo "[$(date '+%H:%M:%S')] train final_skill exists, skipping to eval"
else
    echo "[$(date '+%H:%M:%S')] starting train..."
    set -a && source .env && set +a && OPENAI_AGENTS_DISABLE_TRACING=1 \
    .venv/bin/python -m pipeline.g2b_training \
        --bench spreadsheet --model gpt-5.4 \
        --K 4 --batch-size 4 --n-train 32 \
        --batch-schedule fixed-updates --n-iterations 8 \
        --concurrency 2 --batch-seed 0 --training-seed 0 \
        --method g2b-skill --config-tag SAPR-A5-SS54-N1-seed0 \
        --enable-sapr
    echo "[$(date '+%H:%M:%S')] train done"
fi

# Phase 2: 3 eval reruns
echo "[$(date '+%H:%M:%S')] starting 3 eval reruns..."
SK="${RUN_DIR}/train/final_skill"
for r in 1 2 3; do
    OUT="${RUN_DIR}/eval_r${r}"
    if [ -f "${OUT}/eval_summary.json" ]; then
        HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
        echo "[$(date '+%H:%M:%S')] eval_r${r} exists hg=${HG}, skip"
        continue
    fi
    echo "[$(date '+%H:%M:%S')] eval_r${r} starting"
    .venv/bin/python -m runners.stream_runner eval \
        --bench spreadsheet \
        --skill-dir $SK \
        --output-dir $OUT \
        --model gpt-5.4 \
        --master-seed 0 --heldout-seed 42 \
        --executor-concurrency 4 --grader-concurrency 1
    HG=$(.venv/bin/python -c "import json;print(json.load(open('${OUT}/eval_summary.json'))['aggregate']['mean_hard_graded'])")
    echo "[$(date '+%H:%M:%S')] eval_r${r} done hg=${HG}"
done

# Summary
echo ""
echo "=== SAPR-A5 5.4 SS Summary ==="
.venv/bin/python -c "
import json, os, statistics
accs = []
for r in [1,2,3]:
    p=f'results/runs/g2b-skill-spreadsheet_gpt-5.4_SAPR-A5-SS54-N1-seed0/eval_r{r}/eval_summary.json'
    if os.path.exists(p):
        accs.append(json.load(open(p))['aggregate']['mean_hard_graded']*100)
print(f'reruns: {[f\"{a:.1f}\" for a in accs]}')
if len(accs) >= 2:
    print(f'mean = {statistics.mean(accs):.2f}, std = {statistics.stdev(accs):.2f}, spread = {max(accs)-min(accs):.1f}pp')
print(f'reference: v8 5.4 SS = 68/70/69 mean 69.0 std 1.0 (pipeline-mismatched proxy)')
"
echo "=== END $(date) ==="
