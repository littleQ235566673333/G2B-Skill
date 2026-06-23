"""C-topology ablation: avoid_signal grep (behavior-layer detection).

For each rule, scan the v8_plus_neg trace for fail/pass patterns defined in rules.yaml.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


def grep_trace(trace_path: Path, pattern: str, context: str | None = None) -> int:
    if not trace_path.exists():
        return 0
    text = trace_path.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
    if context:
        # Restrict to lines matching context
        ctx_re = re.compile(context, re.IGNORECASE)
        ctx_lines = [ln for ln in text.split("\n") if ctx_re.search(ln)]
        if not ctx_lines:
            return 0
    return len(matches)


def avoid_signal(rule: dict, trace_path: Path) -> tuple[str, dict]:
    """Returns ('avoided' | 'not_avoided' | 'inconclusive', details)."""
    fail_pattern = rule.get("avoid_check", {}).get("fail_pattern")
    pass_pattern = rule.get("avoid_check", {}).get("pass_pattern")
    fail_context = rule.get("avoid_check", {}).get("fail_context")

    if not trace_path.exists():
        return "inconclusive", {"reason": "trace missing"}

    text = trace_path.read_text(encoding="utf-8", errors="replace")
    n_fail = len(re.findall(fail_pattern, text, re.IGNORECASE)) if fail_pattern else 0
    if fail_pattern and fail_context:
        # Require fail_pattern AND fail_context co-located (within 200 chars)
        ctx_re = re.compile(fail_context, re.IGNORECASE)
        fail_re = re.compile(fail_pattern, re.IGNORECASE)
        co_located = 0
        for m in fail_re.finditer(text):
            window = text[max(0, m.start() - 200): m.end() + 200]
            if ctx_re.search(window):
                co_located += 1
        n_fail = co_located

    n_pass = len(re.findall(pass_pattern, text, re.IGNORECASE)) if pass_pattern else 0
    sec = rule.get("avoid_check", {}).get("pass_secondary")
    n_pass_sec = len(re.findall(sec, text, re.IGNORECASE)) if sec else None

    details = {
        "n_fail_pattern_matches": n_fail,
        "n_pass_pattern_matches": n_pass,
        "n_pass_secondary_matches": n_pass_sec,
    }
    if n_fail > 0 and n_pass == 0:
        return "not_avoided", details
    if n_pass > 0 and n_fail == 0:
        return "avoided", details
    if n_pass > 0 and n_fail > 0:
        return "mixed", details
    return "inconclusive", details


def main():
    rules_doc = yaml.safe_load(
        Path("analysis/c_topo_ablation/rules.yaml").read_text(encoding="utf-8")
    )
    summary = json.loads(
        Path("analysis/c_topo_ablation/eval_results/summary.json").read_text(encoding="utf-8")
    )
    summary_by = {(r["condition"], r["case_id"]): r for r in summary}

    rows: list[dict] = []
    for rule in rules_doc["rules"]:
        case_id = rule["case_id"]
        rule_id = rule["rule_id"]
        for cond in ["seed", "v8", "v8_plus_neg"]:
            trace = Path(
                f"analysis/c_topo_ablation/eval_results/{cond}/{case_id}/execution_trace_r0.md"
            )
            verdict, det = avoid_signal(rule, trace)
            outcome = summary_by.get((cond, case_id), {})
            rows.append({
                "rule_id": rule_id,
                "case_id": case_id,
                "condition": cond,
                "avoid_signal": verdict,
                "outcome_pass": outcome.get("is_correct"),
                "details": det,
            })

    # Print tables
    print("=" * 90)
    print(f"{'rule':<6} {'case':<10} {'cond':<14} {'avoid_signal':<14} {'outcome':<10}")
    print("-" * 90)
    for r in rows:
        oc = "PASS" if r["outcome_pass"] else "FAIL" if r["outcome_pass"] is False else "?"
        print(f"{r['rule_id']:<6} {r['case_id']:<10} {r['condition']:<14} {r['avoid_signal']:<14} {oc:<10}")

    # v8_plus_neg specific tally — the test condition
    print("\n=== v8_plus_neg avoid_signal tally ===")
    n_avoided = sum(1 for r in rows if r["condition"] == "v8_plus_neg" and r["avoid_signal"] == "avoided")
    n_mixed = sum(1 for r in rows if r["condition"] == "v8_plus_neg" and r["avoid_signal"] == "mixed")
    n_not = sum(1 for r in rows if r["condition"] == "v8_plus_neg" and r["avoid_signal"] == "not_avoided")
    n_inc = sum(1 for r in rows if r["condition"] == "v8_plus_neg" and r["avoid_signal"] == "inconclusive")
    print(f"  avoided:       {n_avoided}/5")
    print(f"  mixed:         {n_mixed}/5")
    print(f"  not_avoided:   {n_not}/5")
    print(f"  inconclusive:  {n_inc}/5")

    n_pass = sum(1 for r in rows if r["condition"] == "v8_plus_neg" and r["outcome_pass"])
    print(f"\n  outcome_pass:  {n_pass}/5 (v8_plus_neg)")

    # Compare with v8 baseline avoid_signal
    print("\n=== v8 baseline (no negative rules) avoid_signal tally ===")
    for verdict in ["avoided", "mixed", "not_avoided", "inconclusive"]:
        n = sum(1 for r in rows if r["condition"] == "v8" and r["avoid_signal"] == verdict)
        print(f"  {verdict:<14} {n}/5")

    Path("analysis/c_topo_ablation/eval_results/avoid_signals.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\nWrote analysis/c_topo_ablation/eval_results/avoid_signals.json")


if __name__ == "__main__":
    main()
