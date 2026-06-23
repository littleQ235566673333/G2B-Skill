"""C-topo v2 analysis: paired bootstrap CI + median + per-case distribution + verdict.

Reads:
- v8 control 5-seed data from pilot/branch2/branch3 outputs (per-case 5 seeds each)
- v8+neg treatment 5-seed data from v2_main/main_results.json

Computes:
- Per-case Δ_i = p^neg_i - p^v8_i
- mean(Δ) + 95% CI via paired bootstrap (10k resamples)
- median(Δ)
- Per-case Δ distribution
- Apply verdict matrix
- If Branch 3 used: SG-fail rules sensitivity check

Writes: analysis/c_topo_ablation/REPORT_v2.md
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from collections import Counter


def load_v8_control_per_case(pool_cases: list[str]) -> dict[str, list[bool]]:
    """For each case, load 5 v8 pass/fail outcomes from pilot/B2/B3.

    Dedupes by (case_id, seed_idx) — pilot/B2 cases that B3 reused appear in
    multiple files; we keep only one record per seed_idx (pilot wins, then B2,
    then B3) so a case ends up with exactly N_seeds entries, not 2*N.
    """
    sources = [
        "analysis/c_topo_ablation/v2_pilot/pilot_results.json",
        "analysis/c_topo_ablation/v2_branch2/branch2_results.json",
        "analysis/c_topo_ablation/v2_branch3/branch3_results.json",
    ]
    seen: dict[tuple[str, int], dict] = {}
    for fp in sources:
        p = Path(fp)
        if not p.exists():
            continue
        for r in json.loads(p.read_text()):
            if "is_correct" not in r:
                continue
            key = (r["case_id"], r["seed_idx"])
            if key not in seen:
                seen[key] = r

    out: dict[str, list[bool]] = {}
    for cid in pool_cases:
        recs = sorted([r for k, r in seen.items() if k[0] == cid],
                      key=lambda r: r.get("seed_idx", 0))
        out[cid] = [bool(r["is_correct"]) for r in recs[:5]]
    return out


def load_v8_neg_per_case(pool_cases: list[str]) -> dict[str, list[bool]]:
    p = Path("analysis/c_topo_ablation/v2_main/main_results.json")
    if not p.exists():
        return {}
    recs = json.loads(p.read_text())
    out: dict[str, list[bool]] = {}
    for cid in pool_cases:
        crec = sorted([r for r in recs if r.get("case_id")==cid and "is_correct" in r],
                      key=lambda r: r.get("seed_idx", 0))
        out[cid] = [bool(r["is_correct"]) for r in crec[:5]]
    return out


def paired_bootstrap_mean(deltas: list[float], n_resamples: int = 10000,
                           ci: float = 0.95, seed_int: int = 42) -> tuple[float, float, float]:
    """Returns (mean, lo, hi) for paired bootstrap on deltas."""
    rng = random.Random(seed_int)
    n = len(deltas)
    means = []
    for _ in range(n_resamples):
        sample = [deltas[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample)/n)
    means.sort()
    lo_idx = int(n_resamples * (1-ci)/2)
    hi_idx = int(n_resamples * (1 - (1-ci)/2))
    return sum(deltas)/n, means[lo_idx], means[hi_idx-1]


def median_of(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n//2] if n % 2 else (s[n//2 - 1] + s[n//2]) / 2


def main():
    pool = json.loads(Path("analysis/c_topo_ablation/v2_main_pool.json").read_text())
    cases = pool["main_eval_cases"]
    branch_used = pool.get("branch_used", "unknown")
    sg_exact_cases = set(pool.get("sg_exact_cases", []))

    v8_ctrl = load_v8_control_per_case(cases)
    v8_neg = load_v8_neg_per_case(cases)

    rows = []
    for cid in cases:
        c_ctrl = v8_ctrl.get(cid, [])
        c_neg = v8_neg.get(cid, [])
        p_ctrl = sum(c_ctrl) / max(len(c_ctrl), 1)
        p_neg = sum(c_neg) / max(len(c_neg), 1)
        rows.append({
            "case_id": cid,
            "n_ctrl": len(c_ctrl),
            "n_neg": len(c_neg),
            "p_v8": p_ctrl,
            "p_v8_neg": p_neg,
            "delta": p_neg - p_ctrl,
            "is_sg_exact": cid in sg_exact_cases,
        })

    deltas = [r["delta"] for r in rows]
    mean, lo, hi = paired_bootstrap_mean(deltas)
    med = median_of(deltas)
    pos = sum(1 for d in deltas if d > 0)
    neg = sum(1 for d in deltas if d < 0)
    zero = sum(1 for d in deltas if d == 0)

    # Verdict matrix
    if lo > 0 and med > 0 and pos >= len(deltas)/2:
        verdict = "C-topology promoted to paper main contribution"
    elif lo > 0:
        verdict = "inconclusive (concentration flag) — mean lifted by 1-2 cases"
    elif lo <= 0 and hi > 0:
        verdict = "inconclusive — behavior-layer finding stands; C-topology → future work"
    else:
        verdict = "C-topology line retired (pending negative-verdict qualitative)"

    # SG-fail sensitivity (if Branch 3)
    sens = None
    if branch_used == "Branch 3":
        sg_only = [r["delta"] for r in rows if r["is_sg_exact"]]
        if len(sg_only) >= 4:
            sg_mean = sum(sg_only)/len(sg_only)
            ratio = sg_mean / mean if mean != 0 else 0
            both_pos = (lo > 0) and (paired_bootstrap_mean(sg_only)[1] > 0)
            if both_pos and sg_mean >= 0.5 * mean:
                sens = "robust (SG-exact subset agrees with full)"
            elif sg_mean < 0.5 * mean:
                sens = "driven_by_question_only_rules"
            else:
                sens = "ambiguous"
        else:
            sens = f"insufficient_subset_size (n={len(sg_only)})"

    summary = {
        "n_cases": len(cases),
        "mean_delta": mean,
        "ci_lower": lo,
        "ci_upper": hi,
        "median_delta": med,
        "n_positive": pos,
        "n_negative": neg,
        "n_zero": zero,
        "verdict": verdict,
        "sg_exact_sensitivity": sens,
        "branch_used": branch_used,
        "per_case": rows,
    }
    Path("analysis/c_topo_ablation/v2_analysis_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # Print summary
    print("=" * 80)
    print(f"C-Topology v2 Multi-Seed Ablation — N={len(cases)}, Branch={branch_used}")
    print("=" * 80)
    print(f"\nPer-case deltas:")
    print(f"  {'case':<10} {'p_v8':<8} {'p_v8+neg':<10} {'Δ':<8} {'sg_exact':<10}")
    for r in rows:
        print(f"  {r['case_id']:<10} {r['p_v8']:<8.2f} {r['p_v8_neg']:<10.2f} "
              f"{r['delta']:+.2f}    {'Y' if r['is_sg_exact'] else 'N':<10}")

    print(f"\nAggregate:")
    print(f"  mean Δ:          {mean:+.3f}")
    print(f"  95% CI:          [{lo:+.3f}, {hi:+.3f}]")
    print(f"  median Δ:        {med:+.3f}")
    print(f"  positive / zero / negative: {pos} / {zero} / {neg}")
    print(f"\nVerdict: {verdict}")
    if sens:
        print(f"SG-exact sensitivity: {sens}")


if __name__ == "__main__":
    main()
