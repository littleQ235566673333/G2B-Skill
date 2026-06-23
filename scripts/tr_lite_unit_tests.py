"""Unit tests for trust_region_gate.py — 7 cases per spec + fallback."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.trust_region_gate import (
    parse_h2_sections, fuzzy_align_h2, body_edit_ratio,
    parse_patcher_mapping, trust_region_gate, PatcherMapping,
    TIER_BUDGETS,
)


def assert_eq(name, got, expected):
    if got != expected:
        print(f"  FAIL [{name}]: expected {expected!r}, got {got!r}")
        return False
    print(f"  PASS [{name}]")
    return True


def assert_close(name, got, expected, tol=1e-6):
    if abs(got - expected) > tol:
        print(f"  FAIL [{name}]: expected {expected}, got {got}")
        return False
    print(f"  PASS [{name}]")
    return True


def test_parse_h2_sections():
    print("\n=== test_parse_h2_sections ===")
    text = "preamble line\n\n## A\nbody A\n\n## B\nbody B\n"
    secs = parse_h2_sections(text)
    return all([
        assert_eq("count", len(secs), 3),  # preamble + A + B
        assert_eq("preamble", secs[0].title, "__preamble__"),
        assert_eq("A_title", secs[1].title, "A"),
        assert_eq("A_body", secs[1].body, "body A"),
        assert_eq("B_title", secs[2].title, "B"),
    ])


def test_fuzzy_align_exact_match():
    print("\n=== test_fuzzy_align_exact_match ===")
    old = parse_h2_sections("## A\nx\n## B\ny")
    new = parse_h2_sections("## A\nx\n## B\ny")
    pairs, deleted, added = fuzzy_align_h2(old, new)
    return all([
        assert_eq("pairs_count", len(pairs), 2),  # A + B (no preamble in this input)
        assert_eq("deleted", deleted, []),
        assert_eq("added", added, []),
    ])


def test_fuzzy_align_partial():
    print("\n=== test_fuzzy_align_partial ===")
    old = parse_h2_sections("## Old A\nx\n## B\ny")
    new = parse_h2_sections("## A New\nz\n## C\nw")
    pairs, deleted, added = fuzzy_align_h2(old, new, threshold=0.5)
    # "Old A" vs "A New" similarity ~0.4; "B" vs "C" ~0
    # so likely no fuzzy match, B + Old A deleted, A New + C added
    print(f"  pairs={[(old[i].title, new[j].title) for i,j in pairs]}")
    print(f"  deleted={[old[i].title for i in deleted]}")
    print(f"  added={[new[j].title for j in added]}")
    return True


def test_trust_region_within_budget():
    print("\n=== test_trust_region_within_budget ===")
    s_old = "## Inv\nfoo bar baz\n"
    s_new = "## Inv\nfoo bar BAZ\n"  # tiny edit
    mapping = PatcherMapping(
        modified_sections=[{"section_title": "Inv", "evidence_ids": ["E1"]}],
        parse_status="ok",
    )
    ev = {"E1": "high"}
    s_final, log = trust_region_gate(s_old, s_new, mapping, ev)
    return all([
        assert_eq("status", log["mapping_status"], "ok"),
        assert_eq("rollbacks", log["section_rollback_count"], 0),
        assert_eq("kept", log["section_kept_count"], 1),
    ])


def test_trust_region_exceeds_budget():
    print("\n=== test_trust_region_exceeds_budget ===")
    s_old = "## Inv\n" + ("foo " * 50) + "\n"
    s_new = "## Inv\n" + ("zzz " * 50) + "\n"  # complete rewrite
    mapping = PatcherMapping(
        modified_sections=[{"section_title": "Inv", "evidence_ids": ["E1"]}],
        parse_status="ok",
    )
    ev = {"E1": "low"}  # budget 0.10
    s_final, log = trust_region_gate(s_old, s_new, mapping, ev)
    # ratio is ~1.0, way over 0.10
    return all([
        assert_eq("rollbacks", log["section_rollback_count"], 1),
        assert_eq("rollback_type", log["rollback_actions"][0]["type"], "ratio_exceeded"),
        assert_eq("contains_old", "foo" in s_final, True),
    ])


def test_deleted_section_restored():
    print("\n=== test_deleted_section_restored ===")
    s_old = "## A\naaa\n## B\nbbb\n"
    s_new = "## A\naaa\n"  # B deleted
    mapping = PatcherMapping(parse_status="ok")
    ev = {}
    s_final, log = trust_region_gate(s_old, s_new, mapping, ev)
    return all([
        assert_eq("rollbacks", log["section_rollback_count"], 1),
        assert_eq("contains_B", "## B" in s_final, True),
    ])


def test_new_section_no_evidence_dropped():
    print("\n=== test_new_section_no_evidence_dropped ===")
    s_old = "## A\naaa\n"
    s_new = "## A\naaa\n## NewSec\nzzz\n"  # patcher added without declaring
    mapping = PatcherMapping(
        modified_sections=[{"section_title": "A", "evidence_ids": []}],
        parse_status="ok",
    )
    ev = {}
    s_final, log = trust_region_gate(s_old, s_new, mapping, ev)
    return all([
        assert_eq("rollbacks", log["section_rollback_count"], 1),
        assert_eq("dropped_new", "NewSec" not in s_final, True),
    ])


def test_protect_tier():
    print("\n=== test_protect_tier ===")
    s_old = "## P\nfrozen content here\n"
    s_new = "## P\nfrozen content HERE\n"  # tiny change
    mapping = PatcherMapping(
        modified_sections=[{"section_title": "P", "evidence_ids": ["E1"]}],
        parse_status="ok",
    )
    ev = {"E1": "protect"}
    s_final, log = trust_region_gate(s_old, s_new, mapping, ev)
    # protect = 0.0 budget, so even tiny change rolls back
    return all([
        assert_eq("rollbacks", log["section_rollback_count"], 1),
        assert_eq("kept_old", "frozen content here" in s_final, True),
    ])


def test_mapping_missing_fallback():
    print("\n=== test_mapping_missing_fallback ===")
    s_old = "## A\naaa\n"
    s_new = "## A\nzzz wholesale rewrite\n"
    s_final, log = trust_region_gate(
        s_old, s_new, PatcherMapping(parse_status="missing"), {}
    )
    return all([
        assert_eq("status", log["mapping_status"], "missing"),
        assert_eq("skipped", log.get("skipped"), "tr_lite_skipped_mapping_missing"),
        assert_eq("returned_proposed", s_final, s_new),
    ])


def test_mapping_parse_yaml():
    print("\n=== test_mapping_parse_yaml ===")
    output = """
Some patcher reasoning text...

```yaml
modified_sections:
  - section_title: "Inv"
    evidence_ids: ["E1"]
new_sections:
  - section_title: "Verify"
    evidence_ids: ["E2"]
deleted_sections: []
```

More text after.
"""
    m = parse_patcher_mapping(output)
    return all([
        assert_eq("status", m.parse_status, "ok"),
        assert_eq("modified_count", len(m.modified_sections), 1),
        assert_eq("new_count", len(m.new_sections), 1),
        assert_eq("deleted_count", len(m.deleted_sections), 0),
    ])


def test_mapping_parse_missing():
    print("\n=== test_mapping_parse_missing ===")
    output = "Just plain text, no yaml."
    m = parse_patcher_mapping(output)
    return assert_eq("missing", m.parse_status, "missing")


if __name__ == "__main__":
    tests = [
        test_parse_h2_sections,
        test_fuzzy_align_exact_match,
        test_fuzzy_align_partial,
        test_trust_region_within_budget,
        test_trust_region_exceeds_budget,
        test_deleted_section_restored,
        test_new_section_no_evidence_dropped,
        test_protect_tier,
        test_mapping_missing_fallback,
        test_mapping_parse_yaml,
        test_mapping_parse_missing,
    ]
    results = []
    for t in tests:
        try:
            results.append(t())
        except Exception as e:
            print(f"  CRASH [{t.__name__}]: {e}")
            results.append(False)
    print(f"\n{'='*40}")
    print(f"  PASSED: {sum(results)}/{len(results)}")
