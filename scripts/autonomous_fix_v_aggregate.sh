#!/bin/bash
# Phase 5: aggregate results + select badcase tasks for next-iter analysis
# Triggered when 18 evals (9 SS + 9 OOD) all complete

cd /Users/unique/auto_research/Project/G2B-Skill
PHASE_LOG=logs/autonomous/fix_v_phase.log

# Wait for 18 eval results (9 SS + 9 WTQ OOD per FIX-V N=3)
while true; do
  ss_done=0; ood_done=0
  for s in 0 1 2; do
    for r in 1 2 3; do
      sf=results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-V-N3-seed${s}/eval_SS41_r${r}/summary.json
      of=results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-V-N3-seed${s}/eval_WTQ41_OOD_r${r}/summary.json
      [ -f $sf ] && ss_done=$((ss_done+1))
      [ -f $of ] && ood_done=$((ood_done+1))
    done
  done
  echo "[$(date '+%H:%M:%S')] phase5 wait: SS=${ss_done}/9 OOD=${ood_done}/9" >> $PHASE_LOG
  if [ "$ss_done" -eq 9 ] && [ "$ood_done" -eq 9 ]; then break; fi
  sleep 120
done

# Aggregate per-seed mean / std / worst
.venv/bin/python <<'PY' > logs/autonomous/fix_v_results.md 2>&1
import json
from pathlib import Path
import statistics

def load_acc(p):
    try:
        d = json.load(open(p))
        return d.get('accuracy', d.get('overall_accuracy', None))
    except Exception:
        return None

def fmt(xs):
    if not xs: return "—"
    if len(xs) == 1: return f"{xs[0]:.1f}"
    m = statistics.mean(xs)
    s = statistics.stdev(xs) if len(xs) > 1 else 0
    return f"{m:.1f} ± {s:.1f}"

print("# Fix V N=3 Results (autonomous)\n")
print(f"## SS-4.1 in-distribution\n")
print("| Seed | r1 | r2 | r3 | mean ± σ |")
print("|------|----|----|----|----------|")
all_ss = []
per_seed_ss = {}
for s in [0, 1, 2]:
    rs = []
    for r in [1, 2, 3]:
        p = f"results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-V-N3-seed{s}/eval_SS41_r{r}/summary.json"
        a = load_acc(p)
        if a is not None: rs.append(a*100 if a < 1 else a)
    per_seed_ss[s] = rs
    all_ss.extend(rs)
    cells = [f"{x:.1f}" for x in rs] + [""] * (3 - len(rs))
    print(f"| {s} | {cells[0]} | {cells[1]} | {cells[2]} | {fmt(rs)} |")
print(f"| **all** | | | | **{fmt(all_ss)}** |")
print(f"| worst-seed mean | | | | {min(statistics.mean(v) for v in per_seed_ss.values() if v):.1f} |")

print(f"\n## WTQ OOD (SS-trained skill on WTQ heldout)\n")
print("| Seed | r1 | r2 | r3 | mean ± σ |")
print("|------|----|----|----|----------|")
all_ood = []
for s in [0, 1, 2]:
    rs = []
    for r in [1, 2, 3]:
        p = f"results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-V-N3-seed{s}/eval_WTQ41_OOD_r{r}/summary.json"
        a = load_acc(p)
        if a is not None: rs.append(a*100 if a < 1 else a)
    all_ood.extend(rs)
    cells = [f"{x:.1f}" for x in rs] + [""] * (3 - len(rs))
    print(f"| {s} | {cells[0]} | {cells[1]} | {cells[2]} | {fmt(rs)} |")
print(f"| **all** | | | | **{fmt(all_ood)}** |")

# SG NOW comparator
print(f"\n## Baseline (SG NOW same-time reruns)\n")
print("### SS-4.1")
sg_ss = []
for r in [1, 2, 3, 4, 5, 6]:
    if r <= 3:
        p = f"results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r{r}/summary.json"
    else:
        p = f"results/runs/skillgrad_gpt-4.1_ss-gpt41/eval_NOW_TIME_VERIFY_r{r}/summary.json"
    a = load_acc(p)
    if a is not None: sg_ss.append(a*100 if a < 1 else a)
print(f"  N={len(sg_ss)}, {fmt(sg_ss)}")

print("\n### WTQ-4.1")
sg_wtq = []
for r in [1, 2, 3]:
    p = f"results/runs/skillgrad_gpt-4.1_wtq-gpt41/eval_NOW_r{r}/summary.json"
    a = load_acc(p)
    if a is not None: sg_wtq.append(a*100 if a < 1 else a)
print(f"  N={len(sg_wtq)}, {fmt(sg_wtq)}")

# Verdict
print("\n## Verdict\n")
if all_ss:
    fixv_ss_mean = statistics.mean(all_ss)
    sg_ss_mean = statistics.mean(sg_ss) if sg_ss else 38.7
    delta = fixv_ss_mean - sg_ss_mean
    print(f"- SS-4.1: Fix V {fixv_ss_mean:.1f} vs SG NOW {sg_ss_mean:.1f} → Δ {delta:+.1f}pp")
    if all_ss and len(all_ss) > 1:
        sigma = statistics.stdev(all_ss)
        print(f"- inter-seed σ = {sigma:.2f}pp ({'PASS' if sigma < 3 else 'FAIL — variance too high'})")
        worst = min(statistics.mean(v) for v in per_seed_ss.values() if v)
        print(f"- worst-seed mean = {worst:.1f} ({'PASS' if worst >= 38 else 'FAIL — outlier remains'})")

if all_ood:
    fixv_ood_mean = statistics.mean(all_ood)
    sg_wtq_mean = statistics.mean(sg_wtq) if sg_wtq else 73.65
    print(f"- WTQ OOD: Fix V {fixv_ood_mean:.1f} vs SG WTQ {sg_wtq_mean:.1f} → Δ {fixv_ood_mean-sg_wtq_mean:+.1f}pp")

PY

cat logs/autonomous/fix_v_results.md >> $PHASE_LOG
echo "[$(date '+%H:%M:%S')] phase 5 done. results in logs/autonomous/fix_v_results.md" >> $PHASE_LOG
