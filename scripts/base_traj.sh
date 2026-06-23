# Stage 1 — Base-trajectory collection on the evolution pool.
#
# Runs the seed skill on every task in the bench's evolution pool to
# identify which ones it fails to solve. SkillGrad samples training
# mini-batches from this failure pool. Bench-keyed under
#   results/base_trajectories/master_<M>_heldout_<H>/<BENCH>/<MODEL>/
# with a sibling `failure_ids.json`.
#
# Cost: ~$3-5 per 200-task run on gpt-5.4 (varies by bench).
#
# Usage:
#   bash scripts/base_traj.sh                              # spreadsheet, gpt-5.4
#   BENCH=wtq bash scripts/base_traj.sh                    # WTQ bench
#   BENCH=wtq MODEL=gpt-4.1 bash scripts/base_traj.sh

BENCH="${BENCH:-spreadsheet}"
MODEL="${MODEL:-gpt-5.4}"
SKILLS_DIR="${SKILLS_DIR:-seeds}"

python -m runners.stream_runner base-trajectories \
    --bench ${BENCH} \
    --model ${MODEL} \
    --master-seed 0 \
    --heldout-seed 42 \
    --skills-dir ${SKILLS_DIR} \
    --max-turns 20 \
    --executor-concurrency 4 \
    --grader-concurrency 1 \
    "$@"
