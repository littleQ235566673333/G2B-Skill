#!/bin/bash
# Option A: stop A5 seed 0 when A5 seed 1 finishes.
# Copy A5 seed 0's latest iter snapshot as its final_skill (underbaked).
# Then 12 evals + aggregate per pre-reg (with underbaked-A5-s0 caveat).

cd /Users/unique/auto_research/Project/G2B-Skill
PHASE=logs/autonomous/sapr_a0a5_phase.log

# Phase 1: wait for A5 seed 1 final_skill
echo "[$(date '+%H:%M:%S')] [Option A monitor] waiting for A5 seed 1" >> $PHASE
A5_S1_DIR="results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed1"
A5_S0_DIR="results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed0"
A0_S1_DIR="results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A0-N2-seed1"

while [ ! -d "$A5_S1_DIR/train/final_skill" ]; do
  sleep 60
done
echo "[$(date '+%H:%M:%S')] A5 seed 1 done; killing A5 seed 0 + snapshotting" >> $PHASE

# Wait for A0 seed 1 too (should be near-done)
for _ in $(seq 1 10); do
  [ -d "$A0_S1_DIR/train/final_skill" ] && break
  sleep 30
done

# Kill A5 seed 0
ps aux | grep "SAPR-A5-N2-seed0" | grep -v grep | awk '{print $2}' | xargs kill 2>/dev/null
sleep 5

# Snapshot A5 seed 0's last iter as final_skill (underbaked)
LAST_ITER=$(ls -d $A5_S0_DIR/train/iter_*/ 2>/dev/null | sort -V | tail -1)
echo "[$(date '+%H:%M:%S')] A5 seed 0 last completed iter: $LAST_ITER" >> $PHASE
if [ -n "$LAST_ITER" ]; then
  # Use skills/{bench} dir as it reflects post-patch state of last completed iter
  SKILL_LIVE="$A5_S0_DIR/skills"
  if [ -d "$SKILL_LIVE" ]; then
    mkdir -p "$A5_S0_DIR/train/final_skill"
    cp -r "$SKILL_LIVE/"* "$A5_S0_DIR/train/final_skill/"
    echo "[$(date '+%H:%M:%S')] copied $SKILL_LIVE → $A5_S0_DIR/train/final_skill (underbaked)" >> $PHASE
  fi
fi

# Save underbaked metadata
echo "{\"underbaked\": true, \"iter_completed\": \"$(basename $LAST_ITER)\"}" > $A5_S0_DIR/train/UNDERBAKED.json

touch results/sapr_TRAINS_DONE.flag
echo "[$(date '+%H:%M:%S')] TRAINS_DONE; awaiting RESUME flag" >> $PHASE

while [ ! -f results/sapr_RESUME.flag ]; do sleep 60; done
rm -f results/sapr_RESUME.flag results/sapr_TRAINS_DONE.flag
echo "[$(date '+%H:%M:%S')] RESUMED; launching 12 evals" >> $PHASE

# Phase 2: 12 evals
for variant in A0 A5; do
  for s in 0 1; do
    SK=results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-${variant}-N2-seed${s}/train/final_skill
    [ ! -d "$SK" ] && continue
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

# Phase 3: wait + aggregate
while true; do
  d=0
  for variant in A0 A5; do
    for s in 0 1; do
      for r in 1 2 3; do
        [ -f "results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-${variant}-N2-seed${s}/eval_r${r}/eval_summary.json" ] && d=$((d+1))
      done
    done
  done
  echo "[$(date '+%H:%M:%S')] evals: $d/12" >> $PHASE
  if [ $d -eq 12 ]; then break; fi
  sleep 120
done

.venv/bin/python <<'PY' > logs/autonomous/sapr_a0a5_results.md 2>&1
import json
from pathlib import Path
import statistics

def load(p):
    if not Path(p).exists(): return None
    try: return json.load(open(p))['aggregate']['mean_hard_graded']
    except: return None

print("# SAPR A0 vs A5 N=2 Results (Option A — A5 seed 0 underbaked)\n")
print("**CAVEAT: A5 seed 0 was stopped early; final_skill = mid-iter snapshot.\n")
print("Treat A5 seed 0 mean as underestimate of fully-trained A5 seed 0.**\n\n")

a5s0_meta = Path("results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed0/train/UNDERBAKED.json")
if a5s0_meta.exists():
    print(f"A5 seed 0 metadata: {a5s0_meta.read_text()}\n")

results = {"A0": {}, "A5": {}}
for variant in ["A0", "A5"]:
    for s in [0, 1]:
        rs = []
        for r in [1, 2, 3]:
            p = f"results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-{variant}-N2-seed{s}/eval_r{r}/eval_summary.json"
            x = load(p)
            if x is not None: rs.append(x)
        results[variant][s] = rs

print("| Variant | Seed | r1 | r2 | r3 | mean | note |")
print("|---------|------|----|----|----|------|------|")
for v in ["A0", "A5"]:
    for s in [0, 1]:
        rs = results[v][s]
        cells = [f"{x*100:.1f}" for x in rs] + ["—"]*(3-len(rs))
        m = statistics.mean(rs)*100 if rs else 0
        note = "underbaked" if (v == "A5" and s == 0) else ""
        print(f"| {v} | {s} | {cells[0]} | {cells[1]} | {cells[2]} | {m:.1f} | {note} |")

a0_all = results["A0"][0] + results["A0"][1]
a5_all = results["A5"][0] + results["A5"][1]
a0_mean = statistics.mean(a0_all)*100 if a0_all else 0
a5_mean = statistics.mean(a5_all)*100 if a5_all else 0
delta = a5_mean - a0_mean
print(f"\n## Aggregate\n")
print(f"- A0 mean (N=2 × r=3): {a0_mean:.2f}%")
print(f"- A5 mean (N=2 × r=3, seed 0 underbaked): {a5_mean:.2f}%")
print(f"- **Δ = {delta:+.2f}pp**")

# Per-seed
a0_s0 = statistics.mean(results["A0"][0])*100 if results["A0"][0] else 0
a0_s1 = statistics.mean(results["A0"][1])*100 if results["A0"][1] else 0
a5_s0 = statistics.mean(results["A5"][0])*100 if results["A5"][0] else 0
a5_s1 = statistics.mean(results["A5"][1])*100 if results["A5"][1] else 0
d0 = a5_s0 - a0_s0
d1 = a5_s1 - a0_s1
print(f"- Per-seed Δ: seed0={d0:+.2f} (underbaked), seed1={d1:+.2f}")

print(f"\n## Verdict\n")
if delta >= 1.5 and (d0 * d1) > 0 and d0 > 0:
    print("**PRIMARY GATE PASS (with A5 s0 underbake caveat)** → run A5 s0 full to confirm, then N=3 5.4")
elif delta >= 0.5 and (d0 * d1) > 0 and d0 > 0:
    print("**ESCAPE CLAUSE** → finish A5 s0 to full + N=3 confirmatory")
elif d1 >= 1.5 and d0 >= -1.0:
    print("**Mixed signal**: seed1 strong but seed0 underbaked may mask. Re-run A5 s0 full.")
else:
    print("**FAIL** → drop SAPR or invest more")
PY

cat logs/autonomous/sapr_a0a5_results.md >> $PHASE
echo "[$(date '+%H:%M:%S')] verdict done" >> $PHASE
