#!/bin/bash
# Re-run 12 evals with throttled concurrency
# 4 evals parallel × executor-concurrency 2 = 8 simultaneous API calls (not 36)
# Run in 3 waves (4 each), wait for each wave before next

cd /Users/unique/auto_research/Project/G2B-Skill
PHASE=logs/autonomous/sapr_a0a5_phase.log

run_eval () {
  local variant=$1
  local s=$2
  local r=$3
  SK=results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-${variant}-N2-seed${s}/train/final_skill
  OUT=results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-${variant}-N2-seed${s}/eval_r${r}
  set -a && source .env && set +a && OPENAI_AGENTS_DISABLE_TRACING=1 nohup .venv/bin/python -m runners.stream_runner eval \
    --bench spreadsheet --skill-dir $SK \
    --output-dir $OUT \
    --model gpt-4.1 --master-seed 0 --heldout-seed 42 \
    --executor-concurrency 2 --grader-concurrency 1 --max-turns 30 \
    > logs/eval_SAPR_${variant}_seed${s}_r${r}_v2.log 2>&1 &
  disown
}

# All 12 configs
configs=(
  "A0 0 1" "A0 0 2" "A0 0 3"
  "A0 1 1" "A0 1 2" "A0 1 3"
  "A5 0 1" "A5 0 2" "A5 0 3"
  "A5 1 1" "A5 1 2" "A5 1 3"
)

echo "[$(date '+%H:%M:%S')] [eval-rerun] starting 3 waves of 4 evals" >> $PHASE

# Wave 1: 4 evals
for cfg in "${configs[@]:0:4}"; do
  run_eval $cfg
  sleep 8
done
echo "[$(date '+%H:%M:%S')] wave 1 launched (4 evals)" >> $PHASE

# Wait for wave 1 done
while true; do
  d=0
  for cfg in "${configs[@]:0:4}"; do
    variant=$(echo $cfg | awk '{print $1}')
    s=$(echo $cfg | awk '{print $2}')
    r=$(echo $cfg | awk '{print $3}')
    f=results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-${variant}-N2-seed${s}/eval_r${r}/eval_summary.json
    if [ -f "$f" ]; then
      n_total=$(.venv/bin/python -c "import json; print(json.load(open('$f'))['aggregate'].get('n_graded', 0))" 2>/dev/null)
      [ "$n_total" -ge 95 ] && d=$((d+1))
    fi
  done
  echo "[$(date '+%H:%M:%S')] wave 1: $d/4 nearly done" >> $PHASE
  if [ $d -eq 4 ]; then break; fi
  sleep 60
done

# Wave 2
for cfg in "${configs[@]:4:4}"; do
  run_eval $cfg
  sleep 8
done
echo "[$(date '+%H:%M:%S')] wave 2 launched" >> $PHASE

while true; do
  d=0
  for cfg in "${configs[@]:4:4}"; do
    variant=$(echo $cfg | awk '{print $1}')
    s=$(echo $cfg | awk '{print $2}')
    r=$(echo $cfg | awk '{print $3}')
    f=results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-${variant}-N2-seed${s}/eval_r${r}/eval_summary.json
    if [ -f "$f" ]; then
      n_total=$(.venv/bin/python -c "import json; print(json.load(open('$f'))['aggregate'].get('n_graded', 0))" 2>/dev/null)
      [ "$n_total" -ge 95 ] && d=$((d+1))
    fi
  done
  echo "[$(date '+%H:%M:%S')] wave 2: $d/4 nearly done" >> $PHASE
  if [ $d -eq 4 ]; then break; fi
  sleep 60
done

# Wave 3
for cfg in "${configs[@]:8:4}"; do
  run_eval $cfg
  sleep 8
done
echo "[$(date '+%H:%M:%S')] wave 3 launched" >> $PHASE

while true; do
  d=0
  for cfg in "${configs[@]:8:4}"; do
    variant=$(echo $cfg | awk '{print $1}')
    s=$(echo $cfg | awk '{print $2}')
    r=$(echo $cfg | awk '{print $3}')
    f=results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-${variant}-N2-seed${s}/eval_r${r}/eval_summary.json
    if [ -f "$f" ]; then
      n_total=$(.venv/bin/python -c "import json; print(json.load(open('$f'))['aggregate'].get('n_graded', 0))" 2>/dev/null)
      [ "$n_total" -ge 95 ] && d=$((d+1))
    fi
  done
  echo "[$(date '+%H:%M:%S')] wave 3: $d/4 nearly done" >> $PHASE
  if [ $d -eq 4 ]; then break; fi
  sleep 60
done

# Aggregate
.venv/bin/python <<'PY' > logs/autonomous/sapr_a0a5_results.md 2>&1
import json
from pathlib import Path
import statistics

def load(p):
    if not Path(p).exists(): return None
    try: return json.load(open(p))['aggregate']['mean_hard_graded']
    except: return None

print("# SAPR A0 vs A5 N=2 Results (Option A — A5 seed 0 underbaked)\n")
print("CAVEAT: A5 seed 0 final_skill is iter-7 mid-train snapshot (not full 8-iter train).\n\n")

results = {"A0": {}, "A5": {}}
for v in ["A0", "A5"]:
    for s in [0, 1]:
        rs = []
        for r in [1, 2, 3]:
            p = f"results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-{v}-N2-seed{s}/eval_r{r}/eval_summary.json"
            x = load(p)
            if x is not None: rs.append(x)
        results[v][s] = rs

print("| Variant | Seed | r1 | r2 | r3 | mean |")
print("|---------|------|----|----|----|------|")
for v in ["A0", "A5"]:
    for s in [0, 1]:
        rs = results[v][s]
        cells = [f"{x*100:.1f}" for x in rs] + ["—"]*(3-len(rs))
        m = statistics.mean(rs)*100 if rs else 0
        note = " (underbaked)" if (v == "A5" and s == 0) else ""
        print(f"| {v} | {s}{note} | {cells[0]} | {cells[1]} | {cells[2]} | {m:.1f} |")

a0_all = results["A0"][0] + results["A0"][1]
a5_all = results["A5"][0] + results["A5"][1]
a0 = statistics.mean(a0_all)*100 if a0_all else 0
a5 = statistics.mean(a5_all)*100 if a5_all else 0
delta = a5 - a0
print(f"\n## Aggregate\n")
print(f"- A0 mean: {a0:.2f}%")
print(f"- A5 mean: {a5:.2f}%")
print(f"- Δ = {delta:+.2f}pp")

a0s0 = statistics.mean(results["A0"][0])*100 if results["A0"][0] else 0
a0s1 = statistics.mean(results["A0"][1])*100 if results["A0"][1] else 0
a5s0 = statistics.mean(results["A5"][0])*100 if results["A5"][0] else 0
a5s1 = statistics.mean(results["A5"][1])*100 if results["A5"][1] else 0
print(f"- Per-seed Δ: seed0={a5s0-a0s0:+.2f} (s0 underbaked), seed1={a5s1-a0s1:+.2f}")

print(f"\n## Verdict (per pre-reg)\n")
same_dir = (a5s0 > a0s0) and (a5s1 > a0s1)
if delta >= 1.5 and same_dir:
    print("**PRIMARY GATE PASS** → N=3 5.4 main")
elif delta >= 0.5 and same_dir:
    print("**ESCAPE CLAUSE** → N=3 confirmatory")
else:
    print("**FAIL or marginal** → drop SAPR / pivot MBCT")
PY

cat logs/autonomous/sapr_a0a5_results.md >> $PHASE
echo "[$(date '+%H:%M:%S')] aggregate done" >> $PHASE
