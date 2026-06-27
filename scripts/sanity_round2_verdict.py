#!/usr/bin/env python3
"""Round 2 verdict per pre-registered C3' criterion.
Locked criteria (PRE_REGISTRATION_v3.1-PR1.md):
- Find at least one (rule R, fail_mode m1, fail_mode m2) triple where:
  * |adherence_mean(R, m1) - adherence_mean(R, m2)| >= 0.5
  * Mann-Whitney U test p < 0.10
  * each cell has >= 4 datapoints
"""
import json
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.stats import mannwhitneyu

OUT_DIR = Path("results/sanity_adherence")
JUDGEMENTS = OUT_DIR / "judgements_round2.jsonl"


def main():
    # Load applicable+OK judgements
    rows = []
    for line in open(JUDGEMENTS):
        r = json.loads(line)
        if not r.get("ok"): continue
        if r.get("applicable") is False: continue
        adh = r.get("adhered")
        if adh is None or not isinstance(adh, (int, float)): continue
        rows.append({
            "task_id": r["task_id"],
            "seed": r["seed"],
            "fail_mode": r["fail_mode"],
            "rule_id": r["rule_id"],
            "adhered": float(adh),
        })
    print(f"  valid (applicable+ok+numeric): {len(rows)}")

    # Build per (rule, fail_mode) → list of adherence values across all rollouts
    cells = defaultdict(list)
    for r in rows:
        cells[(r["rule_id"], r["fail_mode"])].append(r["adhered"])

    rules = sorted(set(k[0] for k in cells))
    fail_modes = sorted(set(k[1] for k in cells))

    print(f"\n  cell sizes (rule × fail_mode):")
    print(f"  {'rule':<28}", *[f"{m[:18]:<20}" for m in fail_modes])
    for rid in rules:
        line = f"  {rid:<28}"
        for fm in fail_modes:
            n = len(cells.get((rid, fm), []))
            line += f"n={n:<3} mean={np.mean(cells.get((rid, fm), [0])):.2f}     " if n > 0 else f"—".ljust(20)
        print(line)

    # Pre-registered C3' check
    print("\n  Mann-Whitney U test per (rule, fm1, fm2) pair:")
    print(f"  {'rule':<28} {'pair':<40} {'|diff|':<10} {'p':<10} {'verdict':<10}")
    triples = []
    for rid in rules:
        for i, m1 in enumerate(fail_modes):
            for m2 in fail_modes[i+1:]:
                a1 = cells.get((rid, m1), [])
                a2 = cells.get((rid, m2), [])
                if len(a1) < 4 or len(a2) < 4: continue
                diff = abs(np.mean(a1) - np.mean(a2))
                try:
                    _, pv = mannwhitneyu(a1, a2, alternative="two-sided")
                except ValueError:
                    pv = 1.0
                pass_diff = diff >= 0.5
                pass_p = pv < 0.10
                verdict = "PASS" if (pass_diff and pass_p) else ""
                if pass_diff or pv < 0.20:
                    print(f"  {rid:<28} {m1[:15]+' vs '+m2[:15]:<40} {diff:<10.3f} {pv:<10.4f} {verdict:<10}")
                if pass_diff and pass_p:
                    triples.append({
                        "rule": rid, "m1": m1, "m2": m2,
                        "mean1": np.mean(a1), "mean2": np.mean(a2),
                        "n1": len(a1), "n2": len(a2),
                        "diff": diff, "p": pv,
                    })

    print(f"\n  Triples satisfying C3' (|diff|>=0.5 AND p<0.10 AND n>=4 each cell): {len(triples)}")
    for t in triples:
        print(f"    {t['rule']}: {t['m1']}({t['mean1']:.2f}, n={t['n1']}) vs {t['m2']}({t['mean2']:.2f}, n={t['n2']}) | diff={t['diff']:.3f}, p={t['p']:.4f}")

    verdict = "PASS" if len(triples) >= 1 else "FAIL"
    print(f"\n  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  C3' verdict: {verdict}")
    if verdict == "PASS":
        print(f"  → SAPR-v3.1 sanity PASS — proceed to A0 vs A5 quick experiment")
    else:
        print(f"  → SAPR-v3.1 sanity FAIL — pivot to MBCT (no third sanity round)")
    print(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    json.dump({
        "verdict": verdict,
        "triples": triples,
        "n_valid_judgements": len(rows),
        "cell_sizes": {f"{rid}|{fm}": len(cells.get((rid, fm), [])) for rid in rules for fm in fail_modes},
        "cell_means": {f"{rid}|{fm}": float(np.mean(cells[(rid, fm)])) if (rid, fm) in cells else None for rid in rules for fm in fail_modes},
    }, open(OUT_DIR / "verdict_round2.json", "w"), indent=2)


if __name__ == "__main__":
    main()
