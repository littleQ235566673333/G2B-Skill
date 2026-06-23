"""Unit tests for patcher_ops.py."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.patcher_ops import (
    parse_patcher_ops, apply_ops, PatchOp, ALLOWED_OPS,
)


def assert_eq(name, got, expected):
    if got != expected:
        print(f"  FAIL [{name}]: expected {expected!r}, got {got!r}")
        return False
    print(f"  PASS [{name}]")
    return True


def test_parse_ok():
    print("\n=== parse_ok ===")
    out = """Some narrative...

```yaml
operations:
  - op: append_to_section
    section_title: "Quick Start"
    content: "- new bullet"
    evidence_ids: ["E1"]
  - op: add_h2_section
    section_title: "New H2"
    content: "Body"
    evidence_ids: ["E2"]
```

trailing"""
    r = parse_patcher_ops(out)
    return all([
        assert_eq("status", r.parse_status, "ok"),
        assert_eq("count", len(r.ops), 2),
        assert_eq("first_op", r.ops[0].op, "append_to_section"),
        assert_eq("first_evidence", r.ops[0].evidence_ids, ["E1"]),
    ])


def test_parse_missing():
    print("\n=== parse_missing ===")
    r = parse_patcher_ops("nothing yaml here")
    return assert_eq("status", r.parse_status, "missing")


def test_parse_unknown_op_filtered():
    print("\n=== parse_unknown_op_filtered ===")
    out = """```yaml
operations:
  - op: replace_section_body
    section_title: "X"
    content: "wholesale rewrite"
    evidence_ids: ["E1"]
  - op: append_to_section
    section_title: "X"
    content: "ok"
    evidence_ids: ["E1"]
```"""
    r = parse_patcher_ops(out)
    return all([
        assert_eq("status", r.parse_status, "ok"),
        assert_eq("filtered_count", len(r.ops), 1),
        assert_eq("kept", r.ops[0].op, "append_to_section"),
        assert_eq("error_logged", any("replace_section_body" in e for e in r.errors), True),
    ])


def test_apply_append():
    print("\n=== apply_append ===")
    s = "## Q\n- bullet 1\n- bullet 2\n"
    ops = [PatchOp(op="append_to_section", section_title="Q",
                   content="- bullet 3", evidence_ids=["E1"])]
    r = apply_ops(s, ops, {"E1"})
    return all([
        assert_eq("applied", len(r.ops_applied), 1),
        assert_eq("rejected", len(r.ops_rejected), 0),
        assert_eq("contains_old", "- bullet 1" in r.s_final, True),
        assert_eq("contains_new", "- bullet 3" in r.s_final, True),
    ])


def test_apply_add_h2():
    print("\n=== apply_add_h2 ===")
    s = "## Q\nx\n"
    ops = [PatchOp(op="add_h2_section", section_title="New",
                   content="body", evidence_ids=["E2"])]
    r = apply_ops(s, ops, {"E1", "E2"})
    return all([
        assert_eq("applied", len(r.ops_applied), 1),
        assert_eq("contains_new_h2", "## New" in r.s_final, True),
        assert_eq("contains_old_h2", "## Q" in r.s_final, True),
    ])


def test_apply_replace_bullet():
    print("\n=== apply_replace_bullet ===")
    s = "## Q\n- old bullet\n- another\n"
    ops = [PatchOp(op="replace_bullet", section_title="Q",
                   old_text="- old bullet", new_text="- new bullet",
                   evidence_ids=["E1"])]
    r = apply_ops(s, ops, {"E1"})
    return all([
        assert_eq("applied", len(r.ops_applied), 1),
        assert_eq("contains_new", "- new bullet" in r.s_final, True),
        assert_eq("not_old", "- old bullet" not in r.s_final, True),
    ])


def test_apply_evidence_validation():
    print("\n=== apply_evidence_validation ===")
    s = "## Q\nx\n"
    ops = [PatchOp(op="append_to_section", section_title="Q",
                   content="- z", evidence_ids=["E_FAKE"])]
    r = apply_ops(s, ops, {"E1", "E2"})  # E_FAKE not in pool
    return all([
        assert_eq("applied", len(r.ops_applied), 0),
        assert_eq("rejected", len(r.ops_rejected), 1),
        assert_eq("reason_unknown_eid", "unknown evidence_ids" in r.ops_rejected[0][1], True),
    ])


def test_apply_section_not_found():
    print("\n=== apply_section_not_found ===")
    s = "## Q\nx\n"
    ops = [PatchOp(op="append_to_section", section_title="Nonexistent",
                   content="z", evidence_ids=["E1"])]
    r = apply_ops(s, ops, {"E1"})
    return all([
        assert_eq("applied", len(r.ops_applied), 0),
        assert_eq("rejected", len(r.ops_rejected), 1),
    ])


def test_op_type_distribution():
    print("\n=== op_type_distribution ===")
    s = "## Q\n- old\n## R\n- old\n"
    ops = [
        PatchOp(op="append_to_section", section_title="Q", content="- a", evidence_ids=["E1"]),
        PatchOp(op="append_to_section", section_title="R", content="- b", evidence_ids=["E1"]),
        PatchOp(op="add_h2_section", section_title="New", content="x", evidence_ids=["E1"]),
    ]
    r = apply_ops(s, ops, {"E1"})
    return all([
        assert_eq("append_count", r.op_type_counts.get("append_to_section", 0), 2),
        assert_eq("add_h2_count", r.op_type_counts.get("add_h2_section", 0), 1),
    ])


if __name__ == "__main__":
    tests = [
        test_parse_ok, test_parse_missing, test_parse_unknown_op_filtered,
        test_apply_append, test_apply_add_h2, test_apply_replace_bullet,
        test_apply_evidence_validation, test_apply_section_not_found,
        test_op_type_distribution,
    ]
    results = []
    for t in tests:
        try:
            results.append(t())
        except Exception as e:
            print(f"  CRASH [{t.__name__}]: {e}")
            results.append(False)
    print(f"\n{'='*40}\n  PASSED: {sum(results)}/{len(results)}")
