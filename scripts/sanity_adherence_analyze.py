#!/usr/bin/env python3
"""Sanity: 3 binary conditions on within-group adherence variance signal."""
import json
import statistics
from collections import defaultdict
from pathlib import Path

import numpy as np

OUT_DIR = Path("results/sanity_adherence")
JUDGEMENTS_PATH = OUT_DIR / "judgements.jsonl"


def load_judgements():
    rows = []
    for line in open(JUDGEMENTS_PATH):
        d = json.loads(line)
        if not d.get("ok"):
            continue
        if d.get("applicable") is False:
            continue  # skip N/A
        adh = d.get("adhered")
        if adh is None or not isinstance(adh, (int, float)):
            continue
        rows.append({
            "task_id": d["task_id"],
            "seed": d["seed"],
            "fail_mode": d["fail_mode"],
            "rule_id": d["rule_id"],
            "adhered": float(adh),
        })
    return rows


def main():
    rows = load_judgements()
    print(f"  valid judgements: {len(rows)} (after filtering N/A)")

    # Build (rule, task) → list of adherence across rollouts
    by_rt = defaultdict(list)  # (rule_id, task_id) → [adh values]
    fail_mode_of = {}
    for r in rows:
        key = (r["rule_id"], r["task_id"])
        by_rt[key].append(r["adhered"])
        fail_mode_of[r["task_id"]] = r["fail_mode"]

    # data points: per (rule, task), mean and var
    points = []
    for (rid, tid), adhs in by_rt.items():
        if len(adhs) < 2:
            continue  # need at least 2 rollouts for variance
        mean_adh = statistics.mean(adhs)
        var_adh = statistics.variance(adhs) if len(adhs) >= 2 else 0.0
        points.append({
            "rule_id": rid,
            "task_id": tid,
            "fail_mode": fail_mode_of[tid],
            "mean": mean_adh,
            "var": var_adh,
            "n": len(adhs),
        })
    print(f"  (rule, task) data points: {len(points)} (target ~40)")

    # ─── C1: variance dispersion across rules ───
    print("\n## C1: variance dispersion across rules")
    by_rule_var = defaultdict(list)
    for p in points:
        by_rule_var[p["rule_id"]].append(p["var"])
    rule_avg_var = {rid: statistics.mean(vs) for rid, vs in by_rule_var.items()}
    sorted_rules = sorted(rule_avg_var.items(), key=lambda kv: kv[1])
    print("  rule avg variance (sorted):")
    for rid, v in sorted_rules:
        print(f"    {rid}: avg_var={v:.4f}")
    if len(sorted_rules) >= 4:
        n = len(sorted_rules)
        bottom_q = [v for _, v in sorted_rules[: max(1, n // 4)]]
        top_q = [v for _, v in sorted_rules[-max(1, n // 4):]]
        bot_mean = statistics.mean(bottom_q) or 1e-6
        top_mean = statistics.mean(top_q)
        ratio = top_mean / bot_mean if bot_mean > 0 else float("inf")
        c1_pass = ratio >= 2.0
        print(f"  top-25% / bottom-25% var ratio = {ratio:.2f}")
        print(f"  C1 {'PASS' if c1_pass else 'FAIL'} (≥2.0 needed)")
    else:
        print(f"  too few rules ({len(sorted_rules)}); using top vs bottom single-rule")
        v_top = sorted_rules[-1][1]
        v_bot = sorted_rules[0][1] or 1e-6
        ratio = v_top / v_bot if v_bot > 0 else float("inf")
        c1_pass = ratio >= 2.0
        print(f"  top/bot ratio = {ratio:.2f}, C1 {'PASS' if c1_pass else 'FAIL'}")

    # ─── C2: k=3 silhouette in (mean, var) space ───
    print("\n## C2: k=3 silhouette on (mean, var)")
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
        X = np.array([[p["mean"], p["var"]] for p in points])
        # Normalize
        X_std = (X - X.mean(0)) / (X.std(0) + 1e-9)
        km = KMeans(n_clusters=3, n_init=10, random_state=0)
        labels = km.fit_predict(X_std)
        if len(set(labels)) > 1:
            sil = silhouette_score(X_std, labels)
        else:
            sil = -1.0
        c2_pass = sil >= 0.4
        print(f"  silhouette = {sil:.3f}")
        print(f"  C2 {'PASS' if c2_pass else 'FAIL'} (≥0.4 needed)")
        for i, p in enumerate(points):
            p["cluster"] = int(labels[i])
    except ImportError:
        print("  sklearn missing; skipping C2")
        c2_pass = None

    # ─── C3: cluster vs fail_mode alignment ───
    print("\n## C3: cluster × fail_mode contingency (Fisher exact / chi2)")
    if c2_pass is None:
        print("  skipped (need C2 clusters)")
        c3_pass = None
    else:
        try:
            from scipy.stats import fisher_exact, chi2_contingency
            fail_modes = sorted(set(p["fail_mode"] for p in points))
            clusters = sorted(set(p["cluster"] for p in points))
            table = np.zeros((len(clusters), len(fail_modes)), dtype=int)
            for p in points:
                ci = clusters.index(p["cluster"])
                fi = fail_modes.index(p["fail_mode"])
                table[ci][fi] += 1
            print(f"  contingency table (rows=clusters, cols=fail_modes={fail_modes}):")
            print(f"  {table.tolist()}")
            chi2, pv, dof, _ = chi2_contingency(table)
            print(f"  chi2={chi2:.3f}, p={pv:.4f}, dof={dof}")
            c3_pass = pv < 0.05
            print(f"  C3 {'PASS' if c3_pass else 'FAIL'} (p<0.05 needed)")
        except Exception as e:
            print(f"  scipy missing or error: {e}")
            c3_pass = None

    # ─── verdict ───
    print("\n## VERDICT")
    print(f"  C1: {'PASS' if c1_pass else 'FAIL'}")
    print(f"  C2: {'PASS' if c2_pass else 'FAIL'}")
    print(f"  C3: {'PASS' if c3_pass else 'FAIL' if c3_pass is False else 'SKIP'}")
    all_pass = (c1_pass and c2_pass and c3_pass)
    print(f"\n  → SAPR-v3.1 sanity: {'PASS — proceed to A0 vs A5' if all_pass else 'FAIL — pivot'}")

    # save
    json.dump({
        "n_points": len(points),
        "c1_pass": bool(c1_pass) if c1_pass is not None else None,
        "c2_pass": bool(c2_pass) if c2_pass is not None else None,
        "c3_pass": bool(c3_pass) if c3_pass is not None else None,
        "all_pass": bool(all_pass),
        "points": points,
    }, open(OUT_DIR / "sanity_verdict.json", "w"), indent=2, default=str)


if __name__ == "__main__":
    main()
