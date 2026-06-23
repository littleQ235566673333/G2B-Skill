"""Helper: draft skeleton negative rules for c-topo v2 main eval pool.

Reads the stable_fail pool, looks up each case's question + gold, and
writes a YAML template for rule drafting. Each rule is then hand-filled
with the failure-mode text before main eval.

Run AFTER Branch 3 finishes; before main eval starts.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

import yaml


def parse_num(s):
    s = re.sub(r'[$,%\s]', '', str(s) or '')
    try: return float(s)
    except: return None


def main():
    # Combine all filter results
    all_recs = []
    for fp in [
        "analysis/c_topo_ablation/v2_pilot/pilot_results.json",
        "analysis/c_topo_ablation/v2_branch2/branch2_results.json",
        "analysis/c_topo_ablation/v2_branch3/branch3_results.json",
    ]:
        p = Path(fp)
        if p.exists():
            all_recs.extend(json.loads(p.read_text()))

    # Per-case classification
    by_case: dict[str, list[bool]] = {}
    for r in all_recs:
        if "is_correct" not in r: continue
        by_case.setdefault(r["case_id"], []).append(bool(r["is_correct"]))

    sf = [(cid, vals) for cid, vals in by_case.items() if sum(vals) <= 1 and len(vals) == 5]
    sp = [(cid, vals) for cid, vals in by_case.items() if sum(vals) >= 4 and len(vals) == 5]
    print(f"stable_fail: {len(sf)}, stable_pass: {len(sp)}")

    if len(sf) < 8:
        print(f"\nHALT: stable_fail={len(sf)} < 8")
        Path("analysis/c_topo_ablation/v2_main_pool.json").write_text(
            json.dumps({"halt": True, "stable_fail_count": len(sf),
                        "stable_fail_cases": [c for c,_ in sf]},
                       indent=2), encoding="utf-8")
        return

    # Pick top-10 stable_fail (lexical sort = deterministic)
    selected = sorted([cid for cid, _ in sf])[:10]

    # Look up each case's question + gold + SG status
    ds = {e['id']: e for e in json.load(open('data/benchmarks/officeqa/dataset.json'))}
    sg = {r['id']: r for r in json.load(open('results/runs/skillgrad_gpt-5.4_oqa-gpt54-smoke/eval_seed0/eval_summary.json'))['results']}

    rule_template = []
    sg_exact_set = []
    for cid in selected:
        gold = ds[cid]['answer']
        q = ds[cid]['instruction']
        sg_pass = sg[cid]['hard_score']
        # SG exact match check
        gold_n = parse_num(gold)
        # Find SG predicted text
        sg_pred_text = None
        eval_root = Path("results/runs/skillgrad_gpt-5.4_oqa-gpt54-smoke/eval_seed0")
        for sub in eval_root.iterdir():
            if sub.is_dir() and cid in sub.name:
                f = sub / "output.txt"
                if f.exists():
                    sg_pred_text = f.read_text(encoding="utf-8").strip()
                    break
        sg_pred_n = parse_num(sg_pred_text) if sg_pred_text else None
        is_sg_exact = (gold_n is not None and sg_pred_n is not None and abs(gold_n - sg_pred_n) < 1e-9)
        if is_sg_exact: sg_exact_set.append(cid)

        rule_template.append({
            "rule_id": f"R{len(rule_template)+1}",
            "case_id": cid,
            "question_excerpt": q[:300],
            "gold_answer": gold,
            "sg_predicted": sg_pred_text or "",
            "sg_pass": bool(sg_pass),
            "is_sg_exact": is_sg_exact,
            "provenance": "SG_pattern" if is_sg_exact else "question_only",
            "rule_text": "TBD: tailored avoid/instead sentence",
            "avoid_check": {
                "pass_pattern": "TBD: regex matching the prescribed behavior in trace",
            },
        })

    pool = {
        "halt": False,
        "main_eval_cases": selected,
        "stable_fail_count": len(sf),
        "stable_pass_count": len(sp),
        "sg_exact_cases": sg_exact_set,
        "branch_used": "Branch 3",  # since we cascaded
    }
    Path("analysis/c_topo_ablation/v2_main_pool.json").write_text(
        json.dumps(pool, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Selected {len(selected)} cases:")
    for cid in selected: print(f"  {cid} sg_exact={cid in sg_exact_set}")
    print(f"\nSG-exact count: {len(sg_exact_set)} / {len(selected)}")

    rule_path = Path("analysis/c_topo_ablation/v2_rules_template.yaml")
    rule_path.write_text(
        yaml.safe_dump({"rules": rule_template}, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8")
    print(f"\nRule template: {rule_path}")


if __name__ == "__main__":
    main()
