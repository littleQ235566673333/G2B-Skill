#!/bin/bash
# When all 3 SS-5.4 final_skill exist, mirror to wtq/ and launch 18 evals
cd /Users/unique/auto_research/Project/G2B-Skill
PHASE_LOG=logs/autonomous/fix_v_ss54_phase.log
mkdir -p logs/autonomous

# Phase 1: wait for 3 final_skill
echo "[$(date '+%H:%M:%S')] Phase 1: waiting for 3 final_skills" >> $PHASE_LOG
while true; do
  done=0
  for s in 0 1 2; do
    [ -d results/runs/g2b-skill-spreadsheet_gpt-5.4_c-topo-FIX-V-SS54-N3-seed${s}/train/final_skill ] && done=$((done+1))
  done
  echo "[$(date '+%H:%M:%S')] final_skill ready: $done/3" >> $PHASE_LOG
  if [ "$done" -eq 3 ]; then break; fi
  sleep 180
done

# Phase 2: mirror xlsx skill into wtq/ for each
echo "[$(date '+%H:%M:%S')] Phase 2: mirroring xlsx → wtq for OOD" >> $PHASE_LOG
for s in 0 1 2; do
  bash scripts/mirror_skill_for_wtq_ood.sh \
    results/runs/g2b-skill-spreadsheet_gpt-5.4_c-topo-FIX-V-SS54-N3-seed${s}/train/final_skill \
    >> $PHASE_LOG 2>&1
done

# Phase 3: launch 18 evals (9 SS-5.4 + 9 WTQ OOD)
echo "[$(date '+%H:%M:%S')] Phase 3: launching 18 evals" >> $PHASE_LOG
for s in 0 1 2; do
  for r in 1 2 3; do
    SK=results/runs/g2b-skill-spreadsheet_gpt-5.4_c-topo-FIX-V-SS54-N3-seed${s}/train/final_skill
    set -a; source .env; set +a
    OPENAI_AGENTS_DISABLE_TRACING=1 nohup .venv/bin/python -m runners.stream_runner eval \
      --bench spreadsheet --skill-dir $SK \
      --output-dir results/runs/g2b-skill-spreadsheet_gpt-5.4_c-topo-FIX-V-SS54-N3-seed${s}/eval_SS54_r${r} \
      --model gpt-5.4 --master-seed 0 --heldout-seed 42 \
      --executor-concurrency 3 --grader-concurrency 1 --max-turns 30 \
      > logs/eval_FIXV_SS54_seed${s}_r${r}.log 2>&1 &
    disown
    sleep 8
    OPENAI_AGENTS_DISABLE_TRACING=1 nohup .venv/bin/python -m runners.stream_runner eval \
      --bench wtq --skill-dir $SK \
      --output-dir results/runs/g2b-skill-spreadsheet_gpt-5.4_c-topo-FIX-V-SS54-N3-seed${s}/eval_WTQ54_OOD_r${r} \
      --model gpt-5.4 --master-seed 0 --heldout-seed 42 \
      --executor-concurrency 3 --grader-concurrency 1 --max-turns 30 \
      > logs/eval_FIXV_SS54_seed${s}_WTQ_OOD_r${r}.log 2>&1 &
    disown
    sleep 8
  done
done

echo "[$(date '+%H:%M:%S')] all 18 evals launched" >> $PHASE_LOG

# Phase 4: wait for all 18 to complete + aggregate
while true; do
  done_ss=0; done_ood=0
  for s in 0 1 2; do
    for r in 1 2 3; do
      [ -f results/runs/g2b-skill-spreadsheet_gpt-5.4_c-topo-FIX-V-SS54-N3-seed${s}/eval_SS54_r${r}/eval_summary.json ] && done_ss=$((done_ss+1))
      [ -f results/runs/g2b-skill-spreadsheet_gpt-5.4_c-topo-FIX-V-SS54-N3-seed${s}/eval_WTQ54_OOD_r${r}/eval_summary.json ] && done_ood=$((done_ood+1))
    done
  done
  echo "[$(date '+%H:%M:%S')] phase 4: SS=${done_ss}/9 OOD=${done_ood}/9" >> $PHASE_LOG
  if [ "$done_ss" -ge 9 ] && [ "$done_ood" -ge 9 ]; then break; fi
  sleep 180
done

# Phase 5: aggregate report
.venv/bin/python <<'PY' > logs/autonomous/fix_v_ss54_results.md 2>&1
import json
from pathlib import Path
import statistics

def load_acc(p):
    if not p.exists(): return None
    try:
        d = json.load(open(p))
        return d.get('aggregate', {}).get('mean_hard_graded')
    except: return None

def fmt(xs):
    if not xs: return "—"
    if len(xs) == 1: return f"{xs[0]*100:.1f}"
    m = statistics.mean(xs)*100
    s = statistics.stdev(xs)*100 if len(xs) > 1 else 0
    return f"{m:.1f} ± {s:.1f}"

print("# Fix V N=3 SS-5.4 Results\n")
print("## SS-5.4 in-distribution\n")
print("| Seed | r1 | r2 | r3 | mean |")
print("|------|----|----|----|------|")
all_ss = []
per_seed = {}
for s in [0, 1, 2]:
    rs = []
    for r in [1, 2, 3]:
        p = Path(f"results/runs/g2b-skill-spreadsheet_gpt-5.4_c-topo-FIX-V-SS54-N3-seed{s}/eval_SS54_r{r}/eval_summary.json")
        a = load_acc(p)
        if a is not None: rs.append(a)
    per_seed[s] = rs
    all_ss.extend(rs)
    cells = [f"{x*100:.1f}" for x in rs] + ["—"]*(3-len(rs))
    print(f"| {s} | {cells[0]} | {cells[1]} | {cells[2]} | {fmt(rs)} |")
print(f"| **all** | | | | **{fmt(all_ss)}** |")

print("\n## WTQ OOD\n")
print("| Seed | r1 | r2 | r3 | mean |")
print("|------|----|----|----|------|")
all_ood = []
for s in [0, 1, 2]:
    rs = []
    for r in [1, 2, 3]:
        p = Path(f"results/runs/g2b-skill-spreadsheet_gpt-5.4_c-topo-FIX-V-SS54-N3-seed{s}/eval_WTQ54_OOD_r{r}/eval_summary.json")
        a = load_acc(p)
        if a is not None: rs.append(a)
    all_ood.extend(rs)
    cells = [f"{x*100:.1f}" for x in rs] + ["—"]*(3-len(rs))
    print(f"| {s} | {cells[0]} | {cells[1]} | {cells[2]} | {fmt(rs)} |")
print(f"| **all** | | | | **{fmt(all_ood)}** |")

print("\n## Same-time baseline (v8 SS-5.4 = SG parity proxy)\n")
v8 = []
for r in [1, 2, 3]:
    p = Path(f"results/runs/g2b-v8_gpt-5.4/eval_NOW_TIME_VERIFY_SS54_r{r}/eval_summary.json")
    a = load_acc(p)
    if a is not None: v8.append(a)
print(f"  v8 SS-5.4 r1-r3: {fmt(v8)}")

print("\n## Verdict\n")
if all_ss and v8:
    fixv = statistics.mean(all_ss)*100
    base = statistics.mean(v8)*100
    print(f"- SS-5.4: Fix V {fixv:.1f} vs v8 (=SG) {base:.1f} → Δ {fixv-base:+.1f}pp")
    print(f"- Anchor SG SS-5.4 = 69.3% → Fix V Δ {fixv-69.3:+.1f}pp")
    if len(all_ss) > 1:
        print(f"- inter-seed σ = {statistics.stdev([statistics.mean(v)*100 for v in per_seed.values() if v]):.2f}pp")
PY

echo "[$(date '+%H:%M:%S')] aggregate done" >> $PHASE_LOG
