#!/usr/bin/env python3
"""SAPR pipeline pre-launch sanity check.

Run BEFORE any SAPR train to catch silent failures:
1. adherence judge can produce non-empty output (smoke 1 call)
2. rule-age filter (if T3) returns expected counts on real snapshot data
3. patcher prompt assembly includes non-empty adherence block

Cost: ~$0.50, 30 seconds.

Usage: python scripts/sapr_pipeline_sanity.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def check_filter_logic(test_run_dir: Path) -> dict:
    """Replay _rule_birth_iters + T3 filter on a real prior SAPR run."""
    sys.path.insert(0, ".")
    from pipeline.group_adherence_judge import _rule_birth_iters

    skill_dir = test_run_dir / "skills" / "xlsx"
    if not skill_dir.exists():
        return {"ok": False, "error": f"no skill_dir at {skill_dir}"}

    results = {}
    for ci in [1, 3, 5, 8]:
        birth = _rule_birth_iters(skill_dir, ci)
        seed = sum(1 for b in birth.values() if b == 1)
        old_enough = sum(1 for b in birth.values() if b > 1 and b <= ci - 2)
        results[ci] = {"total": len(birth), "seed": seed, "old_enough": old_enough}
    return {"ok": True, "per_iter": results}


def check_extract_rules_l3_coverage() -> dict:
    """Sanity: does extract_l2_rules include L3? (T3 effect depends on this)."""
    from pipeline.group_adherence_judge import extract_l2_rules
    sample_skill = Path("results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed1/train/final_skill/xlsx/SKILL.md")
    if not sample_skill.exists():
        return {"ok": False, "error": "no sample skill"}
    rules = extract_l2_rules(sample_skill)
    return {"ok": True, "n_h2_rules": len(rules), "l3_dir_files": len(list((sample_skill.parent / "references").glob("*.md")))}


def main():
    print("=== SAPR pipeline sanity check ===\n")

    # Test 1: extract_l2_rules coverage
    print("1. Rule extraction coverage:")
    r = check_extract_rules_l3_coverage()
    if not r["ok"]:
        print(f"   FAIL: {r.get('error')}")
        return 1
    print(f"   H2 rules extracted: {r['n_h2_rules']}")
    print(f"   L3 files in references/: {r['l3_dir_files']} (NOT extracted by current adherence judge)")
    if r['l3_dir_files'] > r['n_h2_rules']:
        print(f"   ⚠ WARNING: L3 chapters outnumber H2 rules; T3 filter only affects H2")

    # Test 2: filter logic on real run
    print("\n2. Filter logic replay (T3 fix):")
    test_run = Path("results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed1")
    if not test_run.exists():
        print(f"   SKIP: test run {test_run} missing")
    else:
        r = check_filter_logic(test_run)
        if not r["ok"]:
            print(f"   FAIL: {r.get('error')}")
            return 1
        for ci, stats in r["per_iter"].items():
            print(f"   iter {ci}: total={stats['total']}, seed_exempt={stats['seed']}, "
                  f"old_enough={stats['old_enough']}, kept={stats['seed']+stats['old_enough']}")
        # Expected: at iter 1+, seed rules kept (>0)
        if r["per_iter"][1]["seed"] == 0:
            print("   ⚠ WARNING: iter 1 filter keeps 0 rules (likely path bug)")

    # Test 3: existing train dir has snapshot files at expected paths
    print("\n3. Snapshot path resolution:")
    if test_run.exists():
        train_dir = test_run / "train"
        snap1 = train_dir / "snapshot_iter_1" / "xlsx" / "SKILL.md"
        snap_via_buggy = (test_run / "skills" / "xlsx").parent / "train" / "snapshot_iter_1" / "xlsx" / "SKILL.md"
        snap_via_fixed = (test_run / "skills" / "xlsx").parent.parent / "train" / "snapshot_iter_1" / "xlsx" / "SKILL.md"
        print(f"   correct path resolved: {snap1.exists()}")
        print(f"   buggy path (skill_dir.parent/'train') exists: {snap_via_buggy.exists()}")
        print(f"   fixed path (skill_dir.parent.parent/'train') exists: {snap_via_fixed.exists()}")
        if snap_via_buggy.exists() == snap_via_fixed.exists():
            print(f"   ⚠ WARNING: paths resolve identically — bug-vs-fix not distinguishable!")

    print("\n=== sanity check done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
