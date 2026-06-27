#!/bin/bash
# Auto-eval N=2 SAPR quick exp when all 4 trains finish
cd /Users/unique/auto_research/Project/G2B-Skill
PHASE=logs/autonomous/sapr_a0a5_phase.log
mkdir -p logs/autonomous

echo "[$(date '+%H:%M:%S')] waiting for 4 trains" >> $PHASE
while true; do
  done=0
  for s in 0 1; do
    [ -d "results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A0-N2-seed$s/train/final_skill" ] && done=$((done+1))
    [ -d "results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed$s/train/final_skill" ] && done=$((done+1))
  done
  echo "[$(date '+%H:%M:%S')] $done/4 trains done" >> $PHASE
  if [ $done -eq 4 ]; then break; fi
  sleep 180
done

# Launch 12 evals (4 trains × 3 reruns)
echo "[$(date '+%H:%M:%S')] launching 12 evals" >> $PHASE
for variant in A0 A5; do
  for s in 0 1; do
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
done
echo "[$(date '+%H:%M:%S')] 12 evals launched" >> $PHASE

# Wait for all evals
while true; do
  d=0
  for variant in A0 A5; do
    for s in 0 1; do
      for r in 1 2 3; do
        [ -f "results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-${variant}-N2-seed${s}/eval_r${r}/eval_summary.json" ] && d=$((d+1))
      done
    done
  done
  echo "[$(date '+%H:%M:%S')] evals done: $d/12" >> $PHASE
  if [ $d -eq 12 ]; then break; fi
  sleep 120
done

# Aggregate verdict per pre-reg
.venv/bin/python <<'PY' > logs/autonomous/sapr_a0a5_results.md 2>&1
import json
from pathlib import Path
import statistics

def load(p):
    if not Path(p).exists(): return None
    try: return json.load(open(p))['aggregate']['mean_hard_graded']
    except: return None

print("# SAPR A0 vs A5 Results (per pre-reg g2b_sapr_a0a5_prereg.md)\n")
results = {"A0": {}, "A5": {}}
for variant in ["A0", "A5"]:
    for s in [0, 1]:
        rs = []
        for r in [1, 2, 3]:
            p = f"results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-{variant}-N2-seed{s}/eval_r{r}/eval_summary.json"
            v = load(p)
            if v is not None: rs.append(v)
        results[variant][s] = rs

print("| Variant | Seed | r1 | r2 | r3 | mean |")
print("|---------|------|----|----|----|------|")
for v in ["A0", "A5"]:
    for s in [0, 1]:
        rs = results[v][s]
        cells = [f"{x*100:.1f}" for x in rs] + ["—"]*(3-len(rs))
        m = statistics.mean(rs)*100 if rs else 0
        print(f"| {v} | {s} | {cells[0]} | {cells[1]} | {cells[2]} | {m:.1f} |")

a0_all = [x for s in [0,1] for x in results["A0"][s]]
a5_all = [x for s in [0,1] for x in results["A5"][s]]
a0_mean = statistics.mean(a0_all)*100 if a0_all else 0
a5_mean = statistics.mean(a5_all)*100 if a5_all else 0
delta = a5_mean - a0_mean
print(f"\n## Aggregate\n")
print(f"- A0 mean (N=2 × r=3 = 6 evals): {a0_mean:.2f}%")
print(f"- A5 mean (N=2 × r=3 = 6 evals): {a5_mean:.2f}%")
print(f"- **Δ = {delta:+.2f}pp**")

# Pre-reg gate
seed0_a0 = statistics.mean(results["A0"][0])*100 if results["A0"][0] else 0
seed0_a5 = statistics.mean(results["A5"][0])*100 if results["A5"][0] else 0
seed1_a0 = statistics.mean(results["A0"][1])*100 if results["A0"][1] else 0
seed1_a5 = statistics.mean(results["A5"][1])*100 if results["A5"][1] else 0
seed0_delta = seed0_a5 - seed0_a0
seed1_delta = seed1_a5 - seed1_a0
same_dir = (seed0_delta * seed1_delta) > 0 and seed0_delta > 0

print(f"- Per-seed Δ: seed0={seed0_delta:+.2f}, seed1={seed1_delta:+.2f}")
print(f"- Same-direction positive: {same_dir}")

print(f"\n## Verdict (per pre-reg)\n")
if delta >= 1.5 and same_dir:
    print("**PRIMARY GATE PASS** → proceed to N=3 full ablation + 4-layer")
elif delta >= 0.5 and same_dir:
    print("**ESCAPE CLAUSE TRIGGERED** → run N=3 confirmatory ($35, 5h)")
else:
    print("**FAIL** → drop SAPR, pivot to MBCT (no third sanity round)")
PY

cat logs/autonomous/sapr_a0a5_results.md >> $PHASE
echo "[$(date '+%H:%M:%S')] aggregate done" >> $PHASE
