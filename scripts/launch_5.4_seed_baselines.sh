#!/usr/bin/env bash
# Launch seed-only baselines on GPT-5.4 for SS + WTQ benches.
# 3 sequential reruns each to match v8 multiseed format.
set -e

LOG=logs/baselines/5.4_seed_baselines.log
exec > >(tee -a $LOG) 2>&1

echo "=== 5.4 seed baselines launch $(date) ==="

run_eval() {
    local bench=$1; local rerun_tag=$2
    local run_dir="results/runs/baseline_${bench}_gpt54_seed"
    local out="${run_dir}/${rerun_tag}"
    mkdir -p "${run_dir}"
    echo "[$(date '+%H:%M:%S')] launching ${bench} ${rerun_tag}"
    .venv/bin/python -m runners.stream_runner eval \
        --bench ${bench} \
        --skill-dir seeds \
        --output-dir ${out} \
        --model gpt-5.4 \
        --master-seed 0 --heldout-seed 42 \
        --executor-concurrency 4 --grader-concurrency 1 \
        2>&1 | tail -5
    echo "[$(date '+%H:%M:%S')] done ${bench} ${rerun_tag}"
}

# SS 5.4 baseline N=3
for tag in eval eval_rerun1 eval_rerun2; do
    run_eval spreadsheet $tag
done

# WTQ 5.4 baseline N=3
for tag in eval eval_rerun1 eval_rerun2; do
    run_eval wtq $tag
done

echo "=== ALL DONE $(date) ==="
