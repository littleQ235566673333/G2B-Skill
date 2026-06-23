"""TR-lite v1 — Trust-Region Gate for skill patcher.

Per Phase 1 spec (2026-06-19):
- Section-level rollback based on declared evidence tiers and edit ratio budgets.
- Coexists with anti-wipe guard (anti-wipe runs first as nuclear backstop;
  TR-lite is sub-threshold fine-tune).
- Fallback: if patcher mapping is missing/unparseable, skip TR-lite for this
  iter (return s_new_proposed unchanged), log "tr_lite_skipped_mapping_missing".
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────

TIER_BUDGETS = {
    "high":    0.50,
    "medium":  0.25,
    "low":     0.10,
    "none":    0.05,
    "protect": 0.00,
}
TIER_RANK = {"protect": 0, "none": 1, "low": 2, "medium": 3, "high": 4}
FUZZY_H2_THRESHOLD = 0.5
ALLOW_SECTION_DELETION = False


# ─────────────────────────────────────────────────────────────────────────
# Section parsing
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class Section:
    title: str
    body: str
    raw_block: str  # full "## title\nbody" preserving original formatting


def parse_h2_sections(text: str) -> list[Section]:
    """Split markdown into H2 sections. Robust to patchers that occasionally
    use H1 instead of H2 — falls back to H1-as-section parsing if no H2 found.

    Preserves the leading non-section preamble as a special section with
    title='__preamble__'.
    """
    # First pass: detect whether the body has any H2 headings
    has_h2 = any(re.match(r"^## +.+$", line) for line in text.split("\n"))
    if has_h2:
        section_re = re.compile(r"^## +(.+?)\s*$")
    else:
        # Fallback: treat H1 as section markers (skipping the first H1 if it
        # looks like a document title, i.e. the first H1 in the file with no
        # later H1s in normal positions).
        section_re = re.compile(r"^# +(.+?)\s*$")

    out = []
    cur_title = "__preamble__"
    cur_body_lines = []
    cur_raw_lines = []
    for line in text.split("\n"):
        m = section_re.match(line)
        if m:
            if cur_body_lines or cur_title != "__preamble__":
                out.append(Section(
                    title=cur_title,
                    body="\n".join(cur_body_lines).strip(),
                    raw_block="\n".join(cur_raw_lines),
                ))
            cur_title = m.group(1)
            cur_body_lines = []
            cur_raw_lines = [line]
        else:
            cur_body_lines.append(line)
            cur_raw_lines.append(line)
    out.append(Section(
        title=cur_title,
        body="\n".join(cur_body_lines).strip(),
        raw_block="\n".join(cur_raw_lines),
    ))
    return out


def normalize_title(t: str) -> str:
    return re.sub(r"[^\w\s]", "", t.lower()).strip()


def title_similarity(a: str, b: str) -> float:
    if a == "__preamble__" and b == "__preamble__":
        return 1.0
    if a == "__preamble__" or b == "__preamble__":
        return 0.0
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def fuzzy_align_h2(old_secs: list[Section], new_secs: list[Section],
                   threshold: float = FUZZY_H2_THRESHOLD):
    """Greedy fuzzy alignment. Returns (pairs, deleted_idxs, added_idxs)
    where pairs are (old_idx, new_idx)."""
    pairs = []
    used_new = set()
    for i, osec in enumerate(old_secs):
        best_j = -1
        best_sim = 0.0
        for j, nsec in enumerate(new_secs):
            if j in used_new:
                continue
            sim = title_similarity(osec.title, nsec.title)
            if sim > best_sim:
                best_sim = sim
                best_j = j
        if best_j >= 0 and best_sim >= threshold:
            pairs.append((i, best_j))
            used_new.add(best_j)
    deleted = [i for i in range(len(old_secs)) if i not in {p[0] for p in pairs}]
    added = [j for j in range(len(new_secs)) if j not in used_new]
    return pairs, deleted, added


def body_edit_ratio(a: str, b: str) -> float:
    if not a and not b:
        return 0.0
    return 1.0 - SequenceMatcher(None, a, b).ratio()


# ─────────────────────────────────────────────────────────────────────────
# Patcher mapping parser
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class PatcherMapping:
    modified_sections: list[dict] = field(default_factory=list)
    new_sections: list[dict] = field(default_factory=list)
    deleted_sections: list[dict] = field(default_factory=list)
    parse_status: str = "ok"  # "ok" | "missing" | "malformed"


MAPPING_BLOCK_RE = re.compile(
    r"```(?:yaml|yml)?\s*\n"
    r"(.*?(?:modified_sections|new_sections|deleted_sections).*?)\n"
    r"```",
    re.DOTALL | re.IGNORECASE,
)


def parse_patcher_mapping(patcher_output: str) -> PatcherMapping:
    """Look for a YAML block in the patcher's text output that declares
    modified_sections / new_sections / deleted_sections.
    Robust to malformed YAML — falls back to PatcherMapping(parse_status='missing')
    if nothing matches.
    """
    if not patcher_output:
        return PatcherMapping(parse_status="missing")

    m = MAPPING_BLOCK_RE.search(patcher_output)
    if not m:
        return PatcherMapping(parse_status="missing")

    yaml_text = m.group(1)
    # Try yaml first; fall back to a simple regex-based parser.
    try:
        import yaml
        data = yaml.safe_load(yaml_text)
        if not isinstance(data, dict):
            return PatcherMapping(parse_status="malformed")
        modified = data.get("modified_sections") or []
        new = data.get("new_sections") or []
        deleted = data.get("deleted_sections") or []
        if not isinstance(modified, list) or not isinstance(new, list) or not isinstance(deleted, list):
            return PatcherMapping(parse_status="malformed")
        return PatcherMapping(modified_sections=modified, new_sections=new,
                              deleted_sections=deleted, parse_status="ok")
    except Exception:
        return PatcherMapping(parse_status="malformed")


def lookup_mapping_entry(mapping: PatcherMapping, section_title: str,
                         which: str) -> Optional[dict]:
    """Find an entry in modified_sections/new_sections/deleted_sections whose
    section_title matches (fuzzy) the given title."""
    target = {
        "modified": mapping.modified_sections,
        "new": mapping.new_sections,
        "deleted": mapping.deleted_sections,
    }[which]
    norm_q = normalize_title(section_title)
    for entry in target:
        if not isinstance(entry, dict):
            continue
        et = entry.get("section_title", "") or ""
        if SequenceMatcher(None, normalize_title(et), norm_q).ratio() >= FUZZY_H2_THRESHOLD:
            return entry
    return None


# ─────────────────────────────────────────────────────────────────────────
# Trust-Region Gate
# ─────────────────────────────────────────────────────────────────────────

def trust_region_gate(
    s_old: str,
    s_new_proposed: str,
    patcher_mapping: PatcherMapping,
    evidence_tiers: dict[str, str],  # evidence_id -> tier
    *,
    fuzzy_threshold: float = FUZZY_H2_THRESHOLD,
    allow_deletion: bool = ALLOW_SECTION_DELETION,
) -> tuple[str, dict]:
    """Apply section-level trust-region constraints.

    Returns (s_final_text, log_dict).

    Fallback rule: if mapping is missing/malformed, return s_new_proposed
    unchanged and log "tr_lite_skipped_mapping_missing" — anti-wipe is the only
    guard for this iter.
    """
    log = {
        "mapping_status": patcher_mapping.parse_status,
        "rollback_actions": [],
        "section_total_count": 0,
        "section_rollback_count": 0,
        "section_kept_count": 0,
    }

    if patcher_mapping.parse_status != "ok":
        log["skipped"] = "tr_lite_skipped_mapping_missing"
        return s_new_proposed, log

    old_secs = parse_h2_sections(s_old)
    new_secs = parse_h2_sections(s_new_proposed)
    pairs, deleted_idx, added_idx = fuzzy_align_h2(old_secs, new_secs, fuzzy_threshold)
    log["section_total_count"] = len(old_secs) + len(added_idx)

    final_secs: list[Section] = []
    matched_old_to_new = {oi: nj for oi, nj in pairs}

    # Iterate over old sections in original order to preserve layout
    for oi, osec in enumerate(old_secs):
        if oi in matched_old_to_new:
            nj = matched_old_to_new[oi]
            nsec = new_secs[nj]
            ratio = body_edit_ratio(osec.body, nsec.body)
            declared = lookup_mapping_entry(patcher_mapping, osec.title, "modified")

            if declared and declared.get("evidence_ids"):
                ev_ids = declared.get("evidence_ids", [])
                tiers = [evidence_tiers.get(eid, "none") for eid in ev_ids]
                tiers = [t for t in tiers if t in TIER_BUDGETS]
                if not tiers:
                    max_tier = "none"
                else:
                    max_tier = max(tiers, key=lambda t: TIER_RANK.get(t, 0))
                budget = TIER_BUDGETS[max_tier]
                reason_label = f"declared:{max_tier}"
            else:
                budget = TIER_BUDGETS["none"]
                reason_label = "undeclared"

            if ratio <= budget + 1e-9:
                final_secs.append(nsec)
                log["section_kept_count"] += 1
            else:
                final_secs.append(osec)
                log["section_rollback_count"] += 1
                log["rollback_actions"].append({
                    "type": "ratio_exceeded",
                    "section": osec.title,
                    "ratio": round(ratio, 3),
                    "budget": budget,
                    "reason": reason_label,
                })
        else:
            # Section in old but not matched in new → deleted
            if allow_deletion:
                # If deletion explicitly declared in mapping, allow
                declared = lookup_mapping_entry(patcher_mapping, osec.title, "deleted")
                if declared:
                    log["rollback_actions"].append({
                        "type": "deletion_allowed",
                        "section": osec.title,
                    })
                    continue  # skip — section is removed
            # default: restore
            final_secs.append(osec)
            log["section_rollback_count"] += 1
            log["rollback_actions"].append({
                "type": "deleted_restored",
                "section": osec.title,
            })

    # Handle added sections
    for nj in added_idx:
        nsec = new_secs[nj]
        if nsec.title == "__preamble__":
            continue  # preamble already accounted for
        declared = lookup_mapping_entry(patcher_mapping, nsec.title, "new")
        if declared and declared.get("evidence_ids"):
            final_secs.append(nsec)
            log["section_kept_count"] += 1
        else:
            log["section_rollback_count"] += 1
            log["rollback_actions"].append({
                "type": "new_no_evidence_dropped",
                "section": nsec.title,
            })

    # Reassemble
    parts = []
    for sec in final_secs:
        if sec.title == "__preamble__":
            parts.append(sec.raw_block)
        else:
            parts.append(sec.raw_block)
    s_final = "\n".join(parts).rstrip() + "\n"

    log["section_rollback_rate"] = (
        log["section_rollback_count"] / log["section_total_count"]
        if log["section_total_count"] > 0 else 0.0
    )
    return s_final, log
