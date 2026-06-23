# Stage 3 — Evaluate a trained skill on the held-out test split.
#
# Cost: ~$3-5 per run (100 test tasks, gpt-5.4).
#
# Usage:
#   bash scripts/eval.sh                              # spreadsheet, gpt-5.4
#   BENCH=wtq bash scripts/eval.sh                    # WTQ bench
#   MODEL=gpt-4.1 bash scripts/eval.sh

BENCH="${BENCH:-spreadsheet}"
MODEL="${MODEL:-gpt-5.4}"
RUN_ID="skillgrad_${MODEL}"

python -m runners.stream_runner eval \
    --bench ${BENCH} \
    --skill-dir results/runs/${RUN_ID}/train/final_skill \
    --output-dir results/runs/${RUN_ID}/eval \
    --model ${MODEL} \
    --master-seed 0 --heldout-seed 42 \
    --executor-concurrency 4 --grader-concurrency 1
