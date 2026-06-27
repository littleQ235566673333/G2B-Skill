#!/bin/bash
# Watch for A5 seed 1 completion, then kill A5 seed 0 + write TRAINS_DONE.flag
# After RESUME, run 9 evals (A0 s0 + A0 s1 + A5 s1, 3 each) — N=1 A5 design.

cd /Users/unique/auto_research/Project/G2B-Skill
PHASE=logs/autonomous/sapr_a0a5_phase.log

# Phase 1: wait for A5 seed 1 final_skill
echo "[$(date '+%H:%M:%S')] [N=1-A5 watcher] waiting for A5 seed 1 to finish" >> $PHASE
while [ ! -d "results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed1/train/final_skill" ]; do
  sleep 60
  iters=$(ls -d results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed1/train/iter_*/ 2>/dev/null | wc -l | tr -d ' ')
  echo "[$(date '+%H:%M:%S')] A5 seed 1 iter=$iters/8" >> $PHASE
done

# Wait for A0 seed 1 too if not done (it should finish around same time)
while [ ! -d "results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A0-N2-seed1/train/final_skill" ]; do
  sleep 30
done

# Kill A5 seed 0 (slowest)
echo "[$(date '+%H:%M:%S')] A5 seed 1 done; killing A5 seed 0" >> $PHASE
ps aux | grep "SAPR-A5-N2-seed0" | grep -v grep | awk '{print $2}' | xargs kill 2>/dev/null
sleep 5

touch results/sapr_TRAINS_DONE.flag
echo "[$(date '+%H:%M:%S')] TRAINS_DONE flag written; awaiting RESUME" >> $PHASE

# Wait for resume
while [ ! -f results/sapr_RESUME.flag ]; do sleep 60; done
rm -f results/sapr_RESUME.flag results/sapr_TRAINS_DONE.flag
echo "[$(date '+%H:%M:%S')] RESUMED; launching 9 evals (A0 s0/s1 + A5 s1, 3 reruns each)" >> $PHASE

# Phase 2: launch 9 evals (skip A5 seed 0 — partial)
for cfg in "A0 0" "A0 1" "A5 1"; do
  variant=$(echo $cfg | awk '{print $1}')
  s=$(echo $cfg | awk '{print $2}')
  SK=results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-${variant}-N2-seed${s}/train/final_skill
  for r in 1 2 3; do
    OUT=results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-${variant}-N2-seed${s}/eval_r${r}
    set -a && source .env && set +a && OPENAI_AGENTS_DISABLE_TRACING=1 nohup .venv/bin/python -m runners.stream_runner eval \
      --bench spreadsheet --skill-dir $SK \
      --output-dir $OUT \
      --model gpt-4.1 --master-seed 0 --heldout-seed 42 \
      --executor-concurrency 3 --grader-concurrency 1 --max-turns 30 \
      > logs/eval_SAPR_${variant}_seed${s}_r${r}.log 2>&1 &
    disown
    sleep 5
  done
done
echo "[$(date '+%H:%M:%S')] 9 evals launched" >> $PHASE

# Phase 3: wait for 9 evals
while true; do
  d=0
  for cfg in "A0 0" "A0 1" "A5 1"; do
    variant=$(echo $cfg | awk '{print $1}')
    s=$(echo $cfg | awk '{print $2}')
    for r in 1 2 3; do
      [ -f "results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-${variant}-N2-seed${s}/eval_r${r}/eval_summary.json" ] && d=$((d+1))
    done
  done
  echo "[$(date '+%H:%M:%S')] evals done: $d/9" >> $PHASE
  if [ $d -eq 9 ]; then break; fi
  sleep 120
done

# Aggregate (N=1 A5 caveat)
.venv/bin/python <<'PY' > logs/autonomous/sapr_a0a5_results.md 2>&1
import json
from pathlib import Path
import statistics

def load(p):
    if not Path(p).exists(): return None
    try: return json.load(open(p))['aggregate']['mean_hard_graded']
    except: return None

print("# SAPR A0 vs A5 — N=1 A5 result (NOT pre-reg PASS)\n")
print("**CAVEAT: A5 seed 0 was stopped mid-train at user's request. This is\n")
print("N=1 A5 vs N=2 A0 — does NOT satisfy pre-reg `same-direction N=2`\n")
print("requirement. Treat as preliminary signal, not paper-grade.**\n\n")

results = {}
for cfg in [("A0", 0), ("A0", 1), ("A5", 1)]:
    v, s = cfg
    rs = []
    for r in [1, 2, 3]:
        p = f"results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-{v}-N2-seed{s}/eval_r{r}/eval_summary.json"
        x = load(p)
        if x is not None: rs.append(x)
    results[cfg] = rs

print("| Variant | Seed | r1 | r2 | r3 | mean |")
print("|---------|------|----|----|----|------|")
for cfg in [("A0", 0), ("A0", 1), ("A5", 1)]:
    v, s = cfg
    rs = results[cfg]
    cells = [f"{x*100:.1f}" for x in rs] + ["—"]*(3-len(rs))
    m = statistics.mean(rs)*100 if rs else 0
    print(f"| {v} | {s} | {cells[0]} | {cells[1]} | {cells[2]} | {m:.1f} |")

a0_all = results[("A0", 0)] + results[("A0", 1)]
a5_all = results[("A5", 1)]
a0_mean = statistics.mean(a0_all)*100 if a0_all else 0
a5_mean = statistics.mean(a5_all)*100 if a5_all else 0
delta = a5_mean - a0_mean
print(f"\n## Aggregate\n")
print(f"- A0 mean (N=2 × r=3 = 6 evals): {a0_mean:.2f}%")
print(f"- A5 mean (N=1 × r=3 = 3 evals): {a5_mean:.2f}%")
print(f"- **Δ = {delta:+.2f}pp**\n")
print(f"**Verdict (informal, NOT pre-reg)**:")
if delta >= 1.5:
    print(f"- positive signal {delta:.2f}pp ≥ 1.5; need full N=2 A5 to confirm before paper")
elif delta >= 0.5:
    print(f"- weak positive {delta:.2f}pp; rerun A5 seed 0 to complete N=2 before deciding")
else:
    print(f"- noisy / negative {delta:.2f}pp; SAPR likely doesn't lift; consider MBCT pivot")
PY

cat logs/autonomous/sapr_a0a5_results.md >> $PHASE
echo "[$(date '+%H:%M:%S')] aggregate done" >> $PHASE
