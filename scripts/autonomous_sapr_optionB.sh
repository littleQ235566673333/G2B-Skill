#!/bin/bash
# Option B: 8 evals (2 reruns × 4 trains) sequential, executor-concurrency 1.
# 2 reruns sufficient for paired comparison; saves 33% time vs 3 reruns.

cd /Users/unique/auto_research/Project/G2B-Skill
PHASE=logs/autonomous/sapr_a0a5_phase.log

run_eval () {
  local variant=$1; local s=$2; local r=$3
  SK=results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-${variant}-N2-seed${s}/train/final_skill
  OUT=results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-${variant}-N2-seed${s}/eval_r${r}
  echo "[$(date '+%H:%M:%S')] start ${variant}-s${s}-r${r}" >> $PHASE
  set -a && source .env && set +a && OPENAI_AGENTS_DISABLE_TRACING=1 .venv/bin/python -m runners.stream_runner eval \
    --bench spreadsheet --skill-dir $SK --output-dir $OUT \
    --model gpt-4.1 --master-seed 0 --heldout-seed 42 \
    --executor-concurrency 1 --grader-concurrency 1 --max-turns 30 \
    > logs/eval_SAPR_${variant}_seed${s}_r${r}_v3.log 2>&1
  echo "[$(date '+%H:%M:%S')] done ${variant}-s${s}-r${r}" >> $PHASE
}

echo "[$(date '+%H:%M:%S')] [Option B sequential] 8 evals serially" >> $PHASE

# Interleave A0/A5 — partial verdict mid-run useful
configs=(
  "A0 0 1" "A5 0 1"
  "A0 1 1" "A5 1 1"
  "A0 0 2" "A5 0 2"
  "A0 1 2" "A5 1 2"
)

for cfg in "${configs[@]}"; do
  run_eval $cfg
done

echo "[$(date '+%H:%M:%S')] all 8 evals done; aggregating" >> $PHASE

.venv/bin/python <<'PY' > logs/autonomous/sapr_a0a5_results.md 2>&1
import json
from pathlib import Path
import statistics

def load(p):
    if not Path(p).exists(): return None
    try: return json.load(open(p))['aggregate']['mean_hard_graded']
    except: return None

print("# SAPR A0 vs A5 — Option B sequential (2 reruns × 4 trains, 8 evals)\n")
print("CAVEATS:\n")
print("- A5 seed 0 final_skill is iter-7 mid-train snapshot (underbaked)\n")
print("- 2 reruns per train (vs original 3) — slightly noisier\n\n")

results = {"A0": {}, "A5": {}}
for v in ["A0", "A5"]:
    for s in [0, 1]:
        rs = []
        for r in [1, 2]:
            p = f"results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-{v}-N2-seed{s}/eval_r{r}/eval_summary.json"
            x = load(p)
            if x is not None: rs.append(x)
        results[v][s] = rs

print("| Variant | Seed | r1 | r2 | mean |")
print("|---------|------|----|----|------|")
for v in ["A0", "A5"]:
    for s in [0, 1]:
        rs = results[v][s]
        cells = [f"{x*100:.1f}" for x in rs] + ["—"]*(2-len(rs))
        m = statistics.mean(rs)*100 if rs else 0
        note = " (underbaked)" if (v == "A5" and s == 0) else ""
        print(f"| {v} | {s}{note} | {cells[0]} | {cells[1]} | {m:.1f} |")

a0_all = results["A0"][0] + results["A0"][1]
a5_all = results["A5"][0] + results["A5"][1]
a0 = statistics.mean(a0_all)*100 if a0_all else 0
a5 = statistics.mean(a5_all)*100 if a5_all else 0
print(f"\n## Aggregate\n")
print(f"- A0 mean (N=2 × r=2 = 4 evals): {a0:.2f}%")
print(f"- A5 mean (N=2 × r=2 = 4 evals): {a5:.2f}%")
print(f"- Δ = {a5-a0:+.2f}pp")

a0s0 = statistics.mean(results["A0"][0])*100 if results["A0"][0] else 0
a0s1 = statistics.mean(results["A0"][1])*100 if results["A0"][1] else 0
a5s0 = statistics.mean(results["A5"][0])*100 if results["A5"][0] else 0
a5s1 = statistics.mean(results["A5"][1])*100 if results["A5"][1] else 0
print(f"- Per-seed Δ: seed0={a5s0-a0s0:+.2f} (s0 underbaked), seed1={a5s1-a0s1:+.2f}")

same_dir = (a5s0 > a0s0) and (a5s1 > a0s1)
delta = a5 - a0
print(f"\n## Verdict (per pre-reg)\n")
if delta >= 1.5 and same_dir:
    print("**PRIMARY GATE PASS** → N=3 5.4 main")
elif delta >= 0.5 and same_dir:
    print("**ESCAPE CLAUSE** → N=3 confirmatory")
else:
    print("**FAIL** → drop SAPR / pivot MBCT")
PY

cat logs/autonomous/sapr_a0a5_results.md >> $PHASE
echo "[$(date '+%H:%M:%S')] verdict written" >> $PHASE
