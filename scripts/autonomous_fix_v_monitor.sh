#!/bin/bash
# Autonomous Fix V monitor
# Phase 1: wait for seed 0 to complete 2 iters, validate enforcement
# Phase 2: launch seed 1 + seed 2 if validation passes
# Phase 3: when all 3 trains done, launch 9 SS evals + 9 WTQ OOD evals
# Phase 4: aggregate report

cd /Users/unique/auto_research/Project/G2B-Skill
mkdir -p logs/autonomous

PHASE_LOG=logs/autonomous/fix_v_phase.log
echo "[$(date '+%H:%M:%S')] Phase 1: monitoring seed 0 for invariant validation" >> $PHASE_LOG

# Phase 1: wait for seed 0 to finish iter 2
SEED0_DIR=results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-V-N3-seed0
while true; do
  iters=$(ls -d $SEED0_DIR/train/iter_*/ 2>/dev/null | wc -l | tr -d ' ')
  if [ "$iters" -ge 2 ]; then
    echo "[$(date '+%H:%M:%S')] seed 0 reached iter $iters" >> $PHASE_LOG
    break
  fi
  sleep 60
done

# Validate enforcement
trigger_count=$(grep -c "PATCH-GUARD.*INVARIANT" logs/g2b_FIX_V_N3_seed0.log 2>/dev/null || echo 0)
sk_lines=$(wc -l < $SEED0_DIR/skills/xlsx/SKILL.md 2>/dev/null || echo 999)
sk_l3=$(ls $SEED0_DIR/skills/xlsx/references/*.md 2>/dev/null | wc -l | tr -d ' ')

echo "[$(date '+%H:%M:%S')] iter=$iters trigger=$trigger_count lines=$sk_lines L3=$sk_l3" >> $PHASE_LOG

# Sanity gate: even without trigger, lines must be ≤150 and L3 ≤12
if [ "$sk_lines" -gt 150 ] || [ "$sk_l3" -gt 12 ]; then
  echo "[$(date '+%H:%M:%S')] FAIL: invariants violated post-iter (lines=$sk_lines L3=$sk_l3)" >> $PHASE_LOG
  echo "STOP: enforcement broken" >> $PHASE_LOG
  exit 1
fi

# Phase 2: launch seed 1 + seed 2
echo "[$(date '+%H:%M:%S')] Phase 2: launching seed 1 + seed 2" >> $PHASE_LOG
for s in 1 2; do
  set -a; source .env; set +a
  nohup .venv/bin/python -m pipeline.g2b_training \
    --bench spreadsheet --model gpt-4.1 \
    --K 4 --batch-size 4 --n-train 32 \
    --batch-schedule fixed-updates --n-iterations 8 \
    --concurrency 2 --batch-seed $s --training-seed $s \
    --method g2b-skill --config-tag c-topo-FIX-V-N3-seed$s \
    > logs/g2b_FIX_V_N3_seed${s}.log 2>&1 &
  disown
  sleep 20
done

# Phase 3: wait for ALL 3 trains complete (final_skill exists)
echo "[$(date '+%H:%M:%S')] Phase 3: waiting for 3 trains complete" >> $PHASE_LOG
while true; do
  done=0
  for s in 0 1 2; do
    [ -d results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-V-N3-seed${s}/train/final_skill ] && done=$((done+1))
  done
  if [ "$done" -eq 3 ]; then
    echo "[$(date '+%H:%M:%S')] all 3 trains complete" >> $PHASE_LOG
    break
  fi
  sleep 120
done

# Phase 4: launch 9 SS evals + 9 WTQ OOD evals
echo "[$(date '+%H:%M:%S')] Phase 4: launching 18 evals" >> $PHASE_LOG
for s in 0 1 2; do
  for r in 1 2 3; do
    SK=results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-V-N3-seed${s}/train/final_skill
    # SS-4.1 in-distribution eval
    set -a; source .env; set +a
    nohup .venv/bin/python -m runners.stream_runner eval \
      --bench spreadsheet --skill-dir $SK \
      --output-dir results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-V-N3-seed${s}/eval_SS41_r${r} \
      --model gpt-4.1 --master-seed 0 --heldout-seed 42 \
      --executor-concurrency 3 --grader-concurrency 1 --max-turns 30 \
      > logs/eval_FIXV_seed${s}_SS41_r${r}.log 2>&1 &
    disown
    sleep 5
    # WTQ OOD eval (test SS-trained skill on WTQ heldout)
    nohup .venv/bin/python -m runners.stream_runner eval \
      --bench wtq --skill-dir $SK \
      --output-dir results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-V-N3-seed${s}/eval_WTQ41_OOD_r${r} \
      --model gpt-4.1 --master-seed 0 --heldout-seed 42 \
      --executor-concurrency 3 --grader-concurrency 1 --max-turns 30 \
      > logs/eval_FIXV_seed${s}_WTQ41_OOD_r${r}.log 2>&1 &
    disown
    sleep 5
  done
done

echo "[$(date '+%H:%M:%S')] all 18 evals launched. monitor will rest." >> $PHASE_LOG
