"""C-topo v3 grep avoid_signal across 5 conditions × 5 cases.

Maps each case to its rule from rules.yaml, then grep pass_pattern in
each condition's trace.
"""
from __future__ import annotations
import json, re
from pathlib import Path
import yaml


def grep_count(trace_path: Path, pattern: str) -> int:
    if not trace_path.exists(): return 0
    text = trace_path.read_text(encoding="utf-8", errors="replace")
    return len(re.findall(pattern, text, re.IGNORECASE | re.MULTILINE))


def main():
    rules = yaml.safe_load(Path("analysis/c_topo_ablation/v2_rules.yaml").read_text())["rules"]
    rule_by_case = {r["case_id"]: r for r in rules}

    cases = ["oqa-112", "oqa-118", "oqa-130", "oqa-14", "oqa-35"]
    conditions = ["Pa", "Pb", "Pc", "Sb", "Sc"]

    rows = []
    for cond in conditions:
        for cid in cases:
            rule = rule_by_case[cid]
            pat = rule["avoid_check"]["pass_pattern"]
            tp = Path(f"analysis/c_topo_ablation/v3_results/{cond}/{cid}/execution_trace_r0.md")
            n = grep_count(tp, pat)
            rows.append({"condition": cond, "case_id": cid, "rule_id": rule["rule_id"],
                         "n_hits": n, "trace_exists": tp.exists()})

    # Print matrix
    print(f"=== avoid_signal grep matrix (n_hits in trace) ===\n")
    print(f"{'cond':<6} {'oqa-112':<10} {'oqa-118':<10} {'oqa-130':<10} {'oqa-14':<10} {'oqa-35':<10} {'avg':<6}")
    summary = {}
    for cond in conditions:
        line = [cond]
        hits = []
        for cid in cases:
            r = next(x for x in rows if x["condition"]==cond and x["case_id"]==cid)
            line.append(str(r["n_hits"]))
            hits.append(r["n_hits"])
        avg = sum(hits) / len(hits)
        line.append(f"{avg:.1f}")
        summary[cond] = {"hits": hits, "avg": avg, "any_hit_count": sum(1 for h in hits if h > 0)}
        print(f"  {' '.join(f'{x:<10}' for x in line)}")

    print(f"\n=== Cases with at least 1 hit per condition ===")
    for cond in conditions:
        s = summary[cond]
        print(f"  {cond}: {s['any_hit_count']}/5 cases hit pattern (avg hits {s['avg']:.1f})")

    # Decision
    pa = summary["Pa"]["any_hit_count"]
    pb = summary["Pb"]["any_hit_count"]
    pc = summary["Pc"]["any_hit_count"]
    sb = summary["Sb"]["any_hit_count"]
    sc = summary["Sc"]["any_hit_count"]

    print(f"\n=== Pre-committed verdict matrix application ===")
    p_movement = (pb >= pa + 2) or (pc >= pa + 2)
    s_movement = (sb >= pa + 2) or (sc >= pa + 2)
    print(f"P movement (pb or pc ≥ pa + 2): {p_movement}")
    print(f"S movement (sb or sc ≥ pa + 2): {s_movement}")

    if p_movement and s_movement:
        verdict = "both contribute; group_patcher needs combined fix"
    elif p_movement and not s_movement:
        verdict = "① placement primary; group_patcher placement fix"
    elif s_movement and not p_movement:
        if sb > sc:
            verdict = "⑤ anchoring primary; group_patcher Why-template"
        else:
            verdict = "③ style primary; group_patcher process-voice generation"
    else:
        verdict = "SKILL.md injection structurally bounded; no patcher fix recovers; C-topology firmly future work"

    print(f"\n→ Verdict: {verdict}")

    out = {
        "matrix": {cond: summary[cond] for cond in conditions},
        "p_movement": p_movement,
        "s_movement": s_movement,
        "verdict": verdict,
    }
    Path("analysis/c_topo_ablation/v3_grep_summary.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote analysis/c_topo_ablation/v3_grep_summary.json")


if __name__ == "__main__":
    main()
