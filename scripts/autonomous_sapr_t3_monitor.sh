#!/bin/bash
# Auto-eval Tuning 3 A5 seed 1 after train completes
# 3 reruns × concurrency 1 via OpenRouter (proven stable last night)
cd /Users/unique/auto_research/Project/G2B-Skill
PHASE=logs/autonomous/sapr_t3_phase.log

echo "[$(date '+%H:%M:%S')] [T3 monitor] waiting for A5+T3 seed 1 train" >> $PHASE

# Wait for train
while true; do
  fs=results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-T3-A5-seed1/train/final_skill
  if [ -d "$fs" ]; then break; fi
  sleep 120
done
echo "[$(date '+%H:%M:%S')] train done, launching 3 evals via OpenRouter" >> $PHASE

for r in 1 2 3; do
  OUT=results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-T3-A5-seed1/eval_r${r}
  : "${OPENAI_API_KEY:?OPENAI_API_KEY env var must be set}"
  export OPENAI_API_KEY
  export OPENAI_BASE_URL=https://openrouter.ai/api/v1
  export HTTPS_PROXY=http://agent.baidu.com:8891
  export HTTP_PROXY=http://agent.baidu.com:8891
  export OPENAI_AGENTS_DISABLE_TRACING=1

  echo "[$(date '+%H:%M:%S')] start eval r${r}" >> $PHASE
  .venv/bin/python -m runners.stream_runner eval \
    --bench spreadsheet \
    --skill-dir results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-T3-A5-seed1/train/final_skill \
    --output-dir $OUT \
    --model gpt-4.1 --master-seed 0 --heldout-seed 42 \
    --executor-concurrency 1 --grader-concurrency 1 --max-turns 30 \
    > logs/eval_SAPR-T3_seed1_r${r}.log 2>&1
  echo "[$(date '+%H:%M:%S')] done eval r${r}" >> $PHASE
done

# Aggregate
.venv/bin/python <<'PY' > logs/autonomous/sapr_t3_results.md 2>&1
import json
from pathlib import Path
import statistics

# A0 seed 1 reference (from earlier run)
A0_S1 = {
    1: 0.37, 2: 0.41, 3: 0.48,
}

A5_T3 = {}
for r in [1, 2, 3]:
    p = Path(f"results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-T3-A5-seed1/eval_r{r}/eval_summary.json")
    if p.exists():
        d = json.load(open(p))
        A5_T3[r] = d['aggregate']['mean_hard_graded']

print("# SAPR Tuning 3 Results (seed 1)\n")
print("| Rerun | A0 (vanilla) | A5+T3 | Δ |")
print("|-------|--------------|-------|---|")
for r in [1, 2, 3]:
    a0 = A0_S1.get(r)
    a5 = A5_T3.get(r)
    if a0 and a5:
        print(f"| r{r} | {a0*100:.1f} | {a5*100:.1f} | {(a5-a0)*100:+.1f} |")

a0_mean = statistics.mean(A0_S1.values())*100
a5_mean = statistics.mean(A5_T3.values())*100 if A5_T3 else 0
if A5_T3:
    a5_vals = [v*100 for v in A5_T3.values()]
    spread = max(a5_vals) - min(a5_vals) if len(a5_vals)>1 else 0
    print(f"\n## Aggregate")
    print(f"- A0 seed 1 mean: {a0_mean:.2f}")
    print(f"- A5+T3 mean: {a5_mean:.2f}")
    print(f"- **Δ = {a5_mean-a0_mean:+.2f}pp**")
    print(f"- A5+T3 max-min spread: {spread:.2f}pp")
    same_dir = all(A5_T3[r]*100 > A0_S1[r]*100 for r in [1,2,3] if r in A5_T3)

    print(f"\n## Pre-reg verdict (TUNING 3 gate)")
    if a5_mean - a0_mean >= 2 and spread <= 6 and same_dir:
        print("**PRIMARY GATE PASS** → SAPR sub-module 立稳，paper ablation 入选")
    elif a5_mean - a0_mean >= 0.5 and spread <= 6 and same_dir:
        print("**ESCAPE CLAUSE** → N=3 confirmatory 或试 Tuning 2")
    else:
        print("**FAIL** → SAPR 归档 negative result，cap optimization 升 P0")
PY

cat logs/autonomous/sapr_t3_results.md >> $PHASE
echo "[$(date '+%H:%M:%S')] verdict written" >> $PHASE
