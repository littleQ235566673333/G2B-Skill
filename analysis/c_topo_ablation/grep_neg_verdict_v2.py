"""C-topo v2 negative-verdict qualitative grep.

For each rule × case in v8_plus_neg runs, grep pass_pattern from rules.yaml
in execution_trace_r0.md across 5 seeds.

Per protocol confound resolution table:
  rule_executed = cases where pass_pattern hits in ≥3/5 seeds
  rule_ignored = cases where pass_pattern hits in ≤1/5 seeds
  - rule_executed ≥7/10 AND rule_ignored ≤2/10 → capability ceiling
  - rule_executed ≤3/10 AND rule_ignored ≥6/10 → rule-following failure
  - else → mixed, unresolvable
"""
from __future__ import annotations
import json, re
from pathlib import Path
import yaml


def grep_seed(trace_path: Path, pattern: str) -> int:
    if not trace_path.exists(): return 0
    text = trace_path.read_text(encoding="utf-8", errors="replace")
    return len(re.findall(pattern, text, re.IGNORECASE | re.MULTILINE))


def main():
    pool = json.loads(Path("analysis/c_topo_ablation/v2_main_pool.json").read_text())
    cases = pool["main_eval_cases"]
    rules = yaml.safe_load(Path("analysis/c_topo_ablation/v2_rules.yaml").read_text())["rules"]
    rule_by_case = {r["case_id"]: r for r in rules}

    per_case: list[dict] = []
    for cid in cases:
        rule = rule_by_case.get(cid)
        if not rule:
            per_case.append({"case_id": cid, "skipped": "no rule"})
            continue
        pat = rule["avoid_check"]["pass_pattern"]

        # 5 seeds of v8+neg traces
        hits_per_seed = []
        for s in range(5):
            tp = Path(f"analysis/c_topo_ablation/v2_main/{cid}_s{s}/execution_trace_r0.md")
            hits_per_seed.append(grep_seed(tp, pat))

        seeds_with_hit = sum(1 for h in hits_per_seed if h > 0)
        if seeds_with_hit >= 3:
            classification = "rule_executed"
        elif seeds_with_hit <= 1:
            classification = "rule_ignored"
        else:
            classification = "ambiguous"
        per_case.append({
            "case_id": cid,
            "rule_id": rule["rule_id"],
            "pass_pattern": pat,
            "hits_per_seed": hits_per_seed,
            "seeds_with_hit": seeds_with_hit,
            "classification": classification,
        })

    n_executed = sum(1 for r in per_case if r.get("classification") == "rule_executed")
    n_ignored = sum(1 for r in per_case if r.get("classification") == "rule_ignored")
    n_amb = sum(1 for r in per_case if r.get("classification") == "ambiguous")

    print(f"=== Negative-verdict qualitative grep ===")
    print(f"{'case':<10} {'rule':<6} {'hits':<20} {'class'}")
    for r in per_case:
        if "classification" not in r: continue
        print(f"  {r['case_id']:<10} {r['rule_id']:<6} {str(r['hits_per_seed']):<20} {r['classification']}")
    print(f"\nrule_executed: {n_executed}/10")
    print(f"rule_ignored:  {n_ignored}/10")
    print(f"ambiguous:     {n_amb}/10")

    # Confound resolution
    if n_executed >= 7 and n_ignored <= 2:
        confound = "capability_ceiling"
        interp = "Rules followed but model still wrong → C-topology mechanism intact, OQA capability bound. Paper case study, do not retire mechanism."
    elif n_executed <= 3 and n_ignored >= 6:
        confound = "rule_following_failure"
        interp = "Executor ignores SKILL.md negative rules → C-topology mechanism broken at executor layer. Retire C-topology line."
    else:
        confound = "mixed_unresolvable"
        interp = "Mixed evidence; do not claim either direction; C-topology → future work."

    print(f"\nConfound resolution: {confound}")
    print(f"Interpretation: {interp}")

    out = {
        "per_case_grep": per_case,
        "n_executed": n_executed,
        "n_ignored": n_ignored,
        "n_ambiguous": n_amb,
        "confound_resolution": confound,
        "interpretation": interp,
    }
    Path("analysis/c_topo_ablation/v2_negative_verdict_grep.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
