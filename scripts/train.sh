# Stage 2 — Train SkillGrad-style on the failure pool from stage 1.
#
# Final skill written to results/runs/<run_id>/train/final_skill/<skill>/.
# Cost: ~$6-15 per run (40 tasks × 4 batch × 10 iter, gpt-5.4).
#
# Usage:
#   bash scripts/train.sh                              # spreadsheet, gpt-5.4
#   BENCH=wtq bash scripts/train.sh                    # WTQ bench
#   MODEL=gpt-4.1 bash scripts/train.sh

BENCH="${BENCH:-spreadsheet}"
MODEL="${MODEL:-gpt-5.4}"
SKILLS_DIR="${SKILLS_DIR:-seeds}"

python -m pipeline.training \
    --bench ${BENCH} \
    --skills-dir ${SKILLS_DIR} \
    --results-root results \
    --method skillgrad \
    --model ${MODEL} \
    --master-seed 0 --heldout-seed 42 --training-seed 0 \
    --n-train 40 --batch-size 4 --max-turns 30 --concurrency 4
