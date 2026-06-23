# Pilot: mixed-group-rate measurement on K rollouts of base-failed tasks.
#
# Defaults: K=4 rollouts × 20 base-failed tasks = 80 trajectories total
# (~4× a single SkillGrad batch; cost rough estimate ~$2-3 on gpt-5.4).
# To run on the full 75 failed tasks pass --n-tasks 0 (~$8-12).
#
# Skill defaults to the SkillGrad-baseline final_skill we already
# trained — so this measures variance in the regime of an *evolved*
# skill. To pilot on the SEED skill instead, point --skill-dir at
# `seeds`.
#
# Usage:
#   bash scripts/g2b_pilot.sh                           # 20 tasks, K=4, final_skill
#   N_TASKS=0 K=4 bash scripts/g2b_pilot.sh             # full 75 failed tasks
#   SKILL_DIR=seeds bash scripts/g2b_pilot.sh           # pilot on seed skill
#   K=8 bash scripts/g2b_pilot.sh                       # K=8 ablation

MODEL="${MODEL:-gpt-5.4}"
K="${K:-4}"
N_TASKS="${N_TASKS:-20}"
# Default: the final_skill from the baseline run we already finished.
# This sits in the sibling SkillGrad project — read-only reference.
SKILL_DIR="${SKILL_DIR:-/Users/unique/auto_research/Project/SkillGrad/results/runs/skillgrad_gpt-5.4/train/final_skill}"

# We need the dataset/split/base_traj artifacts. Symlink them from the
# baseline run so we don't re-collect.
if [ ! -e results ]; then
    ln -s /Users/unique/auto_research/Project/SkillGrad/results results
    echo "Symlinked results/ → SkillGrad/results/"
fi

python -m pipeline.g2b_pilot \
    --skill-dir "${SKILL_DIR}" \
    --model "${MODEL}" \
    --master-seed 0 --heldout-seed 42 \
    --task-pool failed \
    --n-tasks "${N_TASKS}" \
    --K "${K}" \
    --max-turns 30 \
    --concurrency 4 \
    --output-dir "results/pilot/g2b_mixed_rate_K${K}_n${N_TASKS}"
