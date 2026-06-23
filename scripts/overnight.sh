#!/usr/bin/env bash
# Overnight orchestrator (2026-06-18):
#   1. Wait for v5 SS+WTQ to finish (already running)
#   2. Eval v5 on held-out
#   3. (Experiment A) Multi-seed: SS+WTQ at training_seeds {1, 2} with v5 config
#   4. (Experiment B) K=8: SS+WTQ at training_seed=0 with K=8
#   5. Write summary to results/overnight_summary.md
#
# Default config: K=4, n_train=40, batch_size=4, 10 iter unless overridden.
# Total estimated cost: ~$200-250.

set -u
cd /Users/unique/auto_research/Project/G2B-Skill
mkdir -p logs
exec >> logs/overnight.log 2>&1

echo "=== overnight orchestrator started $(date) ==="

wait_for_pid() {
    local pid=$1
    local label=$2
    while kill -0 "$pid" 2>/dev/null; do
        sleep 60
        echo "[$(date '+%H:%M:%S')] still waiting on $label (pid $pid)..."
    done
    echo "[$(date '+%H:%M:%S')] $label (pid $pid) finished"
}

# ── Wait for currently-running v5 trainings ──
SS_V5_PID=$(pgrep -f "g2b_training.*--bench spreadsheet" | head -1 || echo "")
WTQ_V5_PID=$(pgrep -f "g2b_training.*--bench wtq" | head -1 || echo "")
if [ -n "$SS_V5_PID" ]; then wait_for_pid "$SS_V5_PID" "v5-SS-train"; fi
if [ -n "$WTQ_V5_PID" ]; then wait_for_pid "$WTQ_V5_PID" "v5-WTQ-train"; fi

# ── Eval v5 ──
echo
echo "=== v5 eval $(date) ==="

(
  source .venv/bin/activate && OPENAI_AGENTS_DISABLE_TRACING=true PYTHONUNBUFFERED=1 \
    python -m runners.stream_runner eval \
    --bench spreadsheet \
    --skill-dir results/runs/g2b-skill-spreadsheet_gpt-5.4/train/final_skill \
    --output-dir results/runs/g2b-skill-spreadsheet_gpt-5.4/eval \
    --model gpt-5.4 --master-seed 0 --heldout-seed 42 \
    --executor-concurrency 4 --grader-concurrency 1 \
    > logs/eval_ss_v5.log 2>&1
) &
(
  source .venv/bin/activate && OPENAI_AGENTS_DISABLE_TRACING=true PYTHONUNBUFFERED=1 \
    python -m runners.stream_runner eval \
    --bench wtq \
    --skill-dir results/runs/g2b-skill-wtq_gpt-5.4/train/final_skill \
    --output-dir results/runs/g2b-skill-wtq_gpt-5.4/eval \
    --model gpt-5.4 --master-seed 0 --heldout-seed 42 \
    --executor-concurrency 4 --grader-concurrency 1 \
    > logs/eval_wtq_v5.log 2>&1
) &
wait
echo "[$(date '+%H:%M:%S')] v5 evals complete"

mv results/runs/g2b-skill-spreadsheet_gpt-5.4 results/runs/g2b-skill-spreadsheet_gpt-5.4_v5
mv results/runs/g2b-skill-wtq_gpt-5.4 results/runs/g2b-skill-wtq_gpt-5.4_v5

# ── Experiment A: multi-seed (training_seed=1, 2) ──
for seed in 1 2; do
    echo
    echo "=== Experiment A: training_seed=$seed $(date) ==="
    rm -rf results/runs/g2b-skill-spreadsheet_gpt-5.4 results/runs/g2b-skill-wtq_gpt-5.4

    (
      source .venv/bin/activate && OPENAI_AGENTS_DISABLE_TRACING=true PYTHONUNBUFFERED=1 \
        python -m pipeline.g2b_training \
        --bench spreadsheet --skills-dir seeds --results-root results \
        --method g2b-skill --model gpt-5.4 \
        --master-seed 0 --heldout-seed 42 --training-seed "$seed" \
        --n-train 40 --batch-size 4 --K 4 \
        --max-turns 30 --concurrency 4 \
        > "logs/g2b_full_ss_seed${seed}.log" 2>&1
    ) &
    (
      source .venv/bin/activate && OPENAI_AGENTS_DISABLE_TRACING=true PYTHONUNBUFFERED=1 \
        python -m pipeline.g2b_training \
        --bench wtq --skills-dir seeds --results-root results \
        --method g2b-skill --model gpt-5.4 \
        --master-seed 0 --heldout-seed 42 --training-seed "$seed" \
        --n-train 40 --batch-size 4 --K 4 \
        --max-turns 30 --concurrency 4 \
        > "logs/g2b_full_wtq_seed${seed}.log" 2>&1
    ) &
    wait

    (
      source .venv/bin/activate && OPENAI_AGENTS_DISABLE_TRACING=true PYTHONUNBUFFERED=1 \
        python -m runners.stream_runner eval \
        --bench spreadsheet \
        --skill-dir results/runs/g2b-skill-spreadsheet_gpt-5.4/train/final_skill \
        --output-dir results/runs/g2b-skill-spreadsheet_gpt-5.4/eval \
        --model gpt-5.4 --master-seed 0 --heldout-seed 42 \
        --executor-concurrency 4 --grader-concurrency 1 \
        > "logs/eval_ss_seed${seed}.log" 2>&1
    ) &
    (
      source .venv/bin/activate && OPENAI_AGENTS_DISABLE_TRACING=true PYTHONUNBUFFERED=1 \
        python -m runners.stream_runner eval \
        --bench wtq \
        --skill-dir results/runs/g2b-skill-wtq_gpt-5.4/train/final_skill \
        --output-dir results/runs/g2b-skill-wtq_gpt-5.4/eval \
        --model gpt-5.4 --master-seed 0 --heldout-seed 42 \
        --executor-concurrency 4 --grader-concurrency 1 \
        > "logs/eval_wtq_seed${seed}.log" 2>&1
    ) &
    wait

    mv results/runs/g2b-skill-spreadsheet_gpt-5.4 "results/runs/g2b-skill-spreadsheet_gpt-5.4_seed${seed}"
    mv results/runs/g2b-skill-wtq_gpt-5.4 "results/runs/g2b-skill-wtq_gpt-5.4_seed${seed}"
    echo "[$(date '+%H:%M:%S')] seed=$seed complete"
done

# ── Experiment B: K=8 ──
echo
echo "=== Experiment B: K=8 $(date) ==="
rm -rf results/runs/g2b-skill-spreadsheet_gpt-5.4_K8 results/runs/g2b-skill-wtq_gpt-5.4_K8

(
  source .venv/bin/activate && OPENAI_AGENTS_DISABLE_TRACING=true PYTHONUNBUFFERED=1 \
    python -m pipeline.g2b_training \
    --bench spreadsheet --skills-dir seeds --results-root results \
    --method g2b-skill --model gpt-5.4 --config-tag K8 \
    --master-seed 0 --heldout-seed 42 --training-seed 0 \
    --n-train 40 --batch-size 4 --K 8 \
    --max-turns 30 --concurrency 4 \
    > "logs/g2b_full_ss_K8.log" 2>&1
) &
(
  source .venv/bin/activate && OPENAI_AGENTS_DISABLE_TRACING=true PYTHONUNBUFFERED=1 \
    python -m pipeline.g2b_training \
    --bench wtq --skills-dir seeds --results-root results \
    --method g2b-skill --model gpt-5.4 --config-tag K8 \
    --master-seed 0 --heldout-seed 42 --training-seed 0 \
    --n-train 40 --batch-size 4 --K 8 \
    --max-turns 30 --concurrency 4 \
    > "logs/g2b_full_wtq_K8.log" 2>&1
) &
wait

(
  source .venv/bin/activate && OPENAI_AGENTS_DISABLE_TRACING=true PYTHONUNBUFFERED=1 \
    python -m runners.stream_runner eval \
    --bench spreadsheet \
    --skill-dir results/runs/g2b-skill-spreadsheet_gpt-5.4_K8/train/final_skill \
    --output-dir results/runs/g2b-skill-spreadsheet_gpt-5.4_K8/eval \
    --model gpt-5.4 --master-seed 0 --heldout-seed 42 \
    --executor-concurrency 4 --grader-concurrency 1 \
    > "logs/eval_ss_K8.log" 2>&1
) &
(
  source .venv/bin/activate && OPENAI_AGENTS_DISABLE_TRACING=true PYTHONUNBUFFERED=1 \
    python -m runners.stream_runner eval \
    --bench wtq \
    --skill-dir results/runs/g2b-skill-wtq_gpt-5.4_K8/train/final_skill \
    --output-dir results/runs/g2b-skill-wtq_gpt-5.4_K8/eval \
    --model gpt-5.4 --master-seed 0 --heldout-seed 42 \
    --executor-concurrency 4 --grader-concurrency 1 \
    > "logs/eval_wtq_K8.log" 2>&1
) &
wait

# ── Write final summary ──
echo
echo "=== writing summary $(date) ==="
.venv/bin/python <<'PYEOF'
import json
from pathlib import Path
import datetime
out = Path("results/overnight_summary.md")
lines = ["# Overnight orchestrator summary",
         f"Generated: {datetime.datetime.now().isoformat()}",
         "",
         "| run | bench | hard | cell | cost |",
         "|-----|-------|------|------|------|"]
configs = [
    ("v5 seed=0", "g2b-skill-spreadsheet_gpt-5.4_v5", "g2b-skill-wtq_gpt-5.4_v5"),
    ("v5 seed=1", "g2b-skill-spreadsheet_gpt-5.4_seed1", "g2b-skill-wtq_gpt-5.4_seed1"),
    ("v5 seed=2", "g2b-skill-spreadsheet_gpt-5.4_seed2", "g2b-skill-wtq_gpt-5.4_seed2"),
    ("K=8 seed=0", "g2b-skill-spreadsheet_gpt-5.4_K8", "g2b-skill-wtq_gpt-5.4_K8"),
]
for label, ss_dir, wtq_dir in configs:
    for bench, run_dir in [("spreadsheet", ss_dir), ("wtq", wtq_dir)]:
        try:
            ev = json.load(open(f"results/runs/{run_dir}/eval/eval_summary.json"))
            agg = ev["aggregate"]
            hard = agg.get("mean_hard_graded") or agg.get("hard_score") or 0
            cell = agg.get("mean_cell_graded") or agg.get("mean_cell_accuracy") or 0
            cost = ev.get("cost", {}).get("total", {}).get("cost") or 0
            lines.append(f"| {label} | {bench} | {hard:.1%} | {cell:.1%} | ${cost:.2f} |")
        except Exception as e:
            lines.append(f"| {label} | {bench} | ERROR | {e} | - |")
out.write_text("\n".join(lines) + "\n")
print(f"wrote {out}")
PYEOF

touch results/.overnight_done.flag
echo
echo "=== overnight orchestrator DONE $(date) ==="
