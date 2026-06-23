"""TR-lite pre-check: offline analysis of v8+anti-wipe traces.

For each bench (SS, WTQ) with GPT-4.1 + anti-wipe fix, compute per-iter
section-level rewrite metrics. Decide GO/NO-GO on TR-lite implementation.

Layer A: (S_old → S_new_accepted) on snapshot pairs.
Layer B: (S_old → S_new_proposed) using patcher.jsonl write_file calls.

Decision rule:
  GO if high_ratio_rate ≥ 20% OR deleted_rate ≥ 10% (Layer A only).
"""
from __future__ import annotations
import json
import re
import sys
import statistics
from pathlib import Path
from difflib import SequenceMatcher

# ─────────────────────────────────────────────────────────────────────────
# Section parsing
# ─────────────────────────────────────────────────────────────────────────

def parse_h2_sections(text: str) -> list[tuple[str, str]]:
    """Return list of (title, body) for each H2 section in markdown."""
    out = []
    cur_title = None
    cur_body_lines = []
    for line in text.split("\n"):
        m = re.match(r"^## +(.+?)\s*$", line)
        if m:
            if cur_title is not None:
                out.append((cur_title, "\n".join(cur_body_lines).strip()))
            cur_title = m.group(1)
            cur_body_lines = []
        else:
            if cur_title is not None:
                cur_body_lines.append(line)
    if cur_title is not None:
        out.append((cur_title, "\n".join(cur_body_lines).strip()))
    return out


def normalize_title(t: str) -> str:
    return re.sub(r"[^\w\s]", "", t.lower()).strip()


# ─────────────────────────────────────────────────────────────────────────
# Section alignment (fuzzy)
# ─────────────────────────────────────────────────────────────────────────

def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def fuzzy_align(old_secs: list, new_secs: list, threshold: float = 0.7):
    """Return (pairs, deleted_titles, added_titles).

    pairs = list of (old_idx, new_idx) for matched sections.
    """
    pairs = []
    used_new = set()
    deleted = []
    for i, (otitle, _) in enumerate(old_secs):
        best_j = -1
        best_sim = 0.0
        for j, (ntitle, _) in enumerate(new_secs):
            if j in used_new:
                continue
            sim = title_similarity(otitle, ntitle)
            if sim > best_sim:
                best_sim = sim
                best_j = j
        if best_j >= 0 and best_sim >= threshold:
            pairs.append((i, best_j))
            used_new.add(best_j)
        else:
            deleted.append(otitle)
    added = [new_secs[j][0] for j in range(len(new_secs)) if j not in used_new]
    return pairs, deleted, added


# ─────────────────────────────────────────────────────────────────────────
# Edit ratio (body level)
# ─────────────────────────────────────────────────────────────────────────

def body_edit_ratio(a: str, b: str) -> float:
    """1 - SequenceMatcher.ratio() — fraction of content that differs."""
    if not a and not b:
        return 0.0
    return 1.0 - SequenceMatcher(None, a, b).ratio()


# ─────────────────────────────────────────────────────────────────────────
# Per-patch metrics
# ─────────────────────────────────────────────────────────────────────────

def patch_metrics(s_old: str, s_new: str) -> dict:
    old_secs = parse_h2_sections(s_old)
    new_secs = parse_h2_sections(s_new)
    pairs, deleted, added = fuzzy_align(old_secs, new_secs)
    edit_ratios = []
    for oi, nj in pairs:
        r = body_edit_ratio(old_secs[oi][1], new_secs[nj][1])
        edit_ratios.append(r)
    return {
        "n_old_sections": len(old_secs),
        "n_new_sections": len(new_secs),
        "n_matched": len(pairs),
        "n_deleted": len(deleted),
        "n_added": len(added),
        "deleted_titles": deleted,
        "added_titles": added,
        "edit_ratios": edit_ratios,
        "max_section_edit_ratio": max(edit_ratios) if edit_ratios else 0.0,
        "mean_section_edit_ratio": (sum(edit_ratios) / len(edit_ratios)) if edit_ratios else 0.0,
        "has_high_ratio_section": any(r > 0.5 for r in edit_ratios),
    }


if __name__ == "__main__":
    print("module loaded; helpers ready")
