#!/bin/bash
# Launch N=3 full ablation for SAPR — only after A0 vs A5 quick exp PASS
# Per pre-reg: A5 mean - A0 mean ≥ +1.5pp + same direction + regression=0

cd /Users/unique/auto_research/Project/G2B-Skill

# Verify quick exp PASSed
if [ ! -f logs/autonomous/sapr_a0a5_results.md ]; then
  echo "ERROR: quick exp results not found"; exit 1
fi
verdict=$(grep -E "PRIMARY GATE PASS|ESCAPE CLAUSE|FAIL" logs/autonomous/sapr_a0a5_results.md | head -1)
echo "quick exp verdict: $verdict"
if [[ "$verdict" != *PASS* ]] && [[ "$verdict" != *ESCAPE* ]]; then
  echo "quick exp did not PASS — aborting N=3 launch"; exit 1
fi

# Launch N=3 (3 seeds × 2 variants = 6 trains) — GPT-5.4 main backbone
# Per memory feedback_g2b_fix_v_pivot_gpt54: default N=3 target is 5.4,
# 4.1 is only for smoke. Quick exp on 4.1 already passed pre-reg gate.
for s in 0 1 2; do
  for variant in A0 A5; do
    flag=""
    [ "$variant" = "A5" ] && flag="--enable-sapr"
    set -a && source .env && set +a && OPENAI_AGENTS_DISABLE_TRACING=1 nohup .venv/bin/python -m pipeline.g2b_training \
      --bench spreadsheet --model gpt-5.4 \
      --K 4 --batch-size 4 --n-train 32 \
      --batch-schedule fixed-updates --n-iterations 8 \
      --concurrency 2 --batch-seed $s --training-seed $s \
      --method g2b-skill --config-tag SAPR-${variant}-SS54-N3-seed${s} \
      $flag \
      > logs/sapr_n3_ss54_$(echo $variant | tr '[:upper:]' '[:lower:]')_seed${s}.log 2>&1 &
    disown
    sleep 20
  done
done
echo "6 N=3 trains launched on gpt-5.4"
