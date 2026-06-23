"""TR-lite v2 — structured patcher ops contract.

Per Opus 2026-06-20 spec:
- v1 ops: append_to_section, add_h2_section, replace_bullet
- v1 explicitly EXCLUDES replace_section_body (physically prevents 0.96+ rewrites)
- evidence_ids validated against current iter's evidence pool
- op type distribution tracked (catches "schema 合规但精神违背" failure mode)

The patcher outputs a yaml block declaring ops; this module parses, validates,
and applies them to the pre-patch SKILL.md text.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────
# Op schema
# ─────────────────────────────────────────────────────────────────────────

ALLOWED_OPS = {"append_to_section", "add_h2_section", "replace_bullet"}


@dataclass
class PatchOp:
    op: str  # one of ALLOWED_OPS
    section_title: str
    content: str = ""
    old_text: str = ""  # for replace_bullet
    new_text: str = ""  # for replace_bullet
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class OpsParseResult:
    ops: list[PatchOp] = field(default_factory=list)
    parse_status: str = "ok"  # ok | missing | malformed
    raw_yaml: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class OpsApplyResult:
    s_final: str
    ops_applied: list[PatchOp] = field(default_factory=list)
    ops_rejected: list[tuple[PatchOp, str]] = field(default_factory=list)
    op_type_counts: dict = field(default_factory=dict)


OPS_BLOCK_RE = re.compile(
    r"```(?:yaml|yml)?\s*\n"
    r"(.*?(?:operations|patch_operations).*?)\n"
    r"```",
    re.DOTALL | re.IGNORECASE,
)


def parse_patcher_ops(patcher_output: str) -> OpsParseResult:
    """Extract and parse the patcher's yaml ops block.

    Returns OpsParseResult with parse_status in {ok, missing, malformed}.
    """
    if not patcher_output:
        return OpsParseResult(parse_status="missing")

    m = OPS_BLOCK_RE.search(patcher_output)
    if not m:
        return OpsParseResult(parse_status="missing")

    yaml_text = m.group(1)
    try:
        import yaml
        data = yaml.safe_load(yaml_text)
    except Exception as e:
        return OpsParseResult(parse_status="malformed", raw_yaml=yaml_text,
                              errors=[f"yaml parse error: {e}"])

    if not isinstance(data, dict):
        return OpsParseResult(parse_status="malformed", raw_yaml=yaml_text,
                              errors=["root not a dict"])

    raw_ops = data.get("operations") or data.get("patch_operations") or []
    if not isinstance(raw_ops, list):
        return OpsParseResult(parse_status="malformed", raw_yaml=yaml_text,
                              errors=["operations not a list"])

    out: list[PatchOp] = []
    errs: list[str] = []
    for i, raw in enumerate(raw_ops):
        if not isinstance(raw, dict):
            errs.append(f"op {i}: not a dict, skipped")
            continue
        op_type = raw.get("op") or raw.get("operation") or ""
        if op_type not in ALLOWED_OPS:
            errs.append(f"op {i}: unknown op '{op_type}', allowed={sorted(ALLOWED_OPS)}")
            continue
        po = PatchOp(
            op=op_type,
            section_title=str(raw.get("section_title", "")).strip(),
            content=str(raw.get("content", "")),
            old_text=str(raw.get("old_text", "")),
            new_text=str(raw.get("new_text", "")),
            evidence_ids=[str(x) for x in (raw.get("evidence_ids") or [])],
        )
        out.append(po)

    return OpsParseResult(ops=out, parse_status="ok", raw_yaml=yaml_text, errors=errs)


# ─────────────────────────────────────────────────────────────────────────
# Op application
# ─────────────────────────────────────────────────────────────────────────

def _normalize_title(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip().lower())


def _find_section_bounds(text: str, target_title: str) -> Optional[tuple[int, int, int]]:
    """Return (header_line_idx, body_start_idx, body_end_idx) for the target H2.
    None if not found.
    """
    lines = text.split("\n")
    target_norm = _normalize_title(target_title)
    in_section = False
    header_idx = -1
    body_start = -1
    for i, line in enumerate(lines):
        m = re.match(r"^## +(.+?)\s*$", line)
        if m:
            if in_section:
                # End of previous target
                return (header_idx, body_start, i)
            if _normalize_title(m.group(1)) == target_norm:
                header_idx = i
                body_start = i + 1
                in_section = True
        # else: keep scanning
    if in_section:
        return (header_idx, body_start, len(lines))
    return None


def apply_ops(
    s_pre_patch: str,
    ops: list[PatchOp],
    evidence_pool: set[str],
) -> OpsApplyResult:
    """Apply ops sequentially to the pre-patch SKILL.md text.

    Validates evidence_ids against `evidence_pool` (per Opus A: reject ops
    whose evidence_ids reference non-existent evidence).
    """
    text = s_pre_patch
    applied: list[PatchOp] = []
    rejected: list[tuple[PatchOp, str]] = []

    for op in ops:
        # Evidence validation
        if op.evidence_ids:
            unknown = [eid for eid in op.evidence_ids if eid not in evidence_pool]
            if unknown:
                rejected.append((op, f"unknown evidence_ids: {unknown}"))
                continue

        if op.op == "append_to_section":
            bounds = _find_section_bounds(text, op.section_title)
            if bounds is None:
                rejected.append((op, f"section '{op.section_title}' not found"))
                continue
            header_idx, body_start, body_end = bounds
            lines = text.split("\n")
            insert_at = body_end
            # Trim trailing blank lines from body
            while insert_at > body_start and not lines[insert_at - 1].strip():
                insert_at -= 1
            new_lines = lines[:insert_at] + [""] + op.content.rstrip().split("\n") + [""] + lines[insert_at:]
            text = "\n".join(new_lines)
            applied.append(op)

        elif op.op == "add_h2_section":
            if _find_section_bounds(text, op.section_title) is not None:
                rejected.append((op, f"section '{op.section_title}' already exists"))
                continue
            block = f"\n## {op.section_title}\n\n{op.content.rstrip()}\n"
            text = text.rstrip() + "\n" + block
            applied.append(op)

        elif op.op == "replace_bullet":
            if not op.old_text or not op.new_text:
                rejected.append((op, "replace_bullet requires non-empty old_text and new_text"))
                continue
            bounds = _find_section_bounds(text, op.section_title)
            if bounds is None:
                rejected.append((op, f"section '{op.section_title}' not found"))
                continue
            header_idx, body_start, body_end = bounds
            lines = text.split("\n")
            section_text = "\n".join(lines[body_start:body_end])
            if op.old_text not in section_text:
                rejected.append((op, f"old_text not found in section '{op.section_title}'"))
                continue
            new_section = section_text.replace(op.old_text, op.new_text, 1)
            text = "\n".join(lines[:body_start] + new_section.split("\n") + lines[body_end:])
            applied.append(op)
        else:
            rejected.append((op, f"unknown op type '{op.op}'"))

    # Op type distribution (Opus B)
    type_counts: dict[str, int] = {}
    for op in applied:
        type_counts[op.op] = type_counts.get(op.op, 0) + 1

    return OpsApplyResult(
        s_final=text, ops_applied=applied, ops_rejected=rejected,
        op_type_counts=type_counts,
    )
