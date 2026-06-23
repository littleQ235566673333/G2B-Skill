#!/bin/bash
# Step 1 GPT-4.1 transfer: 4 evals in parallel (single-seed first, multi-seed if positive)
# Run after 4 trainings complete.
set -e

cd /Users/unique/auto_research/Project/G2B-Skill

run_eval() {
    local bench=$1
    local run_id=$2
    local out_subdir=$3  # e.g. eval_s0
    PYTHONPATH=. .venv/bin/python -m runners.stream_runner eval \
        --bench "$bench" \
        --skill-dir "results/runs/$run_id/train/final_skill" \
        --output-dir "results/runs/$run_id/$out_subdir" \
        --model gpt-4.1 \
        --master-seed 0 --heldout-seed 42 \
        --executor-concurrency 4 --grader-concurrency 1 2>&1 | tail -8
}

echo "=== seed 0: 4 evals in parallel ==="
run_eval spreadsheet g2b-v8_gpt-4.1_ss-gpt41 eval_seed0 &
PID1=$!
run_eval spreadsheet skillgrad_gpt-4.1_ss-gpt41 eval_seed0 &
PID2=$!
run_eval wtq g2b-v8_gpt-4.1_wtq-gpt41 eval_seed0 &
PID3=$!
run_eval wtq skillgrad_gpt-4.1_wtq-gpt41 eval_seed0 &
PID4=$!

wait $PID1 $PID2 $PID3 $PID4
echo "seed 0 evals done"

echo "=== seeds 1+2: 8 evals in parallel ==="
for seed in 1 2; do
    run_eval spreadsheet g2b-v8_gpt-4.1_ss-gpt41 eval_seed$seed &
    run_eval spreadsheet skillgrad_gpt-4.1_ss-gpt41 eval_seed$seed &
    run_eval wtq g2b-v8_gpt-4.1_wtq-gpt41 eval_seed$seed &
    run_eval wtq skillgrad_gpt-4.1_wtq-gpt41 eval_seed$seed &
done
wait
echo "seeds 1+2 evals done"

echo "=== aggregating multi-seed results ==="
PYTHONPATH=. .venv/bin/python <<'PY'
import json, statistics
from pathlib import Path
runs = [
    ("v8 SS",   "g2b-v8_gpt-4.1_ss-gpt41",       "spreadsheet"),
    ("SG SS",   "skillgrad_gpt-4.1_ss-gpt41",    "spreadsheet"),
    ("v8 WTQ",  "g2b-v8_gpt-4.1_wtq-gpt41",      "wtq"),
    ("SG WTQ",  "skillgrad_gpt-4.1_wtq-gpt41",   "wtq"),
]
for label, rid, bench in runs:
    counts = []
    cells = []
    for seed in [0, 1, 2]:
        sp = Path(f"results/runs/{rid}/eval_seed{seed}/eval_summary.json")
        if not sp.exists(): continue
        agg = json.load(open(sp))["aggregate"]
        if bench == "spreadsheet":
            counts.append(int(agg.get("n_pass_graded", agg.get("n_perfect", 0))))
        else:
            counts.append(int(agg.get("n_pass_graded", agg.get("n_perfect", 0))))
        cells.append(agg.get("mean_cell_graded", agg.get("mean_cell_accuracy", 0)))
    if not counts: continue
    mean_c = sum(counts)/len(counts)
    std_c = statistics.stdev(counts) if len(counts) > 1 else 0
    mean_cell = sum(cells)/len(cells)
    print(f"{label:>8}: hard {counts} → mean {mean_c:.1f} ± {std_c:.1f} | cell mean {mean_cell:.1%}")
PY
