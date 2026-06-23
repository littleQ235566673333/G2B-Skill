# G2B-Skill training (Phase 1+2+3+4 end-to-end).
#
# Per-iter cost: ~K × executor + 3 group-diagnose + 1 group-momentum
# + 1 group-patch.  K=4, batch=4 → ~$1-2 per iter on gpt-5.4
# (rough estimate; real numbers TBD from this run).
#
# Usage:
#   bash scripts/g2b_train.sh                              # spreadsheet, gpt-5.4, K=4
#   BENCH=wtq bash scripts/g2b_train.sh                    # WTQ
#   K=2 bash scripts/g2b_train.sh                          # K=2 ablation
#   N_ITER=2 bash scripts/g2b_train.sh                     # short pilot

BENCH="${BENCH:-spreadsheet}"
MODEL="${MODEL:-gpt-5.4}"
SKILLS_DIR="${SKILLS_DIR:-seeds}"
K="${K:-4}"
N_TRAIN="${N_TRAIN:-40}"
BATCH_SIZE="${BATCH_SIZE:-4}"

EXTRA=()
if [ -n "${N_ITER:-}" ]; then
    EXTRA+=(--batch-schedule fixed-updates --n-iterations "${N_ITER}")
fi

PY="${PY:-.venv/bin/python}"

OPENAI_AGENTS_DISABLE_TRACING=true \
    PYTHONUNBUFFERED=1 \
    "${PY}" -m pipeline.g2b_training \
    --bench "${BENCH}" \
    --skills-dir "${SKILLS_DIR}" \
    --results-root results \
    --method g2b-skill \
    --model "${MODEL}" \
    --master-seed 0 --heldout-seed 42 --training-seed 0 \
    --n-train "${N_TRAIN}" --batch-size "${BATCH_SIZE}" \
    --K "${K}" \
    --max-turns 30 --concurrency 4 \
    "${EXTRA[@]}"
