"""RSM Tier 0 data collector.

Scans all training runs under results/runs/, detects two classes of
SKILL.md wipe events, and emits a structured YAML for spot-check.

Detection signals
-----------------
For each (run, iter N → iter N+1) pair:
  pre_size  = stat(snapshot_iter_N/<bench>/SKILL.md)
  post_size = stat(snapshot_iter_(N+1)/<bench>/SKILL.md)
  wrote_size = max bytes-written-to-SKILL.md in iter_N/patcher.jsonl
              (taken as the patcher's final write attempt)

  wipe_attempted = wrote_size < 0.5 * pre_size  AND  pre_size > 1500
  wipe_survived  = post_size  < 0.5 * pre_size  AND  pre_size > 1500

  Stratum A (anti-wipe engaged): wipe_attempted AND NOT wipe_survived
                                 (revert intercepted)
  Stratum B (no anti-wipe / silent wipe): wipe_survived
                                 (drop persisted into snapshot)

Filling rules
-------------
  drop_pct          = (post - pre) / pre * 100
  deleted_rule_texts:
     - Stratum B: line-level diff snap_N vs snap_(N+1), keep top 3 deletions
     - Stratum A: parse iter_N/patcher.jsonl message events for what the
       patcher REASONED about deleting; tag as "(reverted)"
  originating_case_id_if_recoverable:
     - For each deleted rule line: search prior iter_M/patcher.jsonl
       message events; if a rule with matching prefix appeared in a patch
       message anchored to a case id, attach it. Else "unknown".
  next_iter_batch_task_ids = training_results.json[iter N+1]["batch"]
  prev/next_iter_pass_count = training_results.json[iter N/N+1]["pre_correct"]
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path
from typing import Optional

import yaml


WIPE_THRESH_FRAC = 0.5   # post < 50% of pre → wipe
MIN_PRE_BYTES = 1500     # ignore tiny-skill iters


def _find_skill_md(snapshot_dir: Path) -> Optional[Path]:
    """Find the SKILL.md inside snapshot_iter_N/<bench>/ — bench dir name varies."""
    if not snapshot_dir.exists():
        return None
    for sub in snapshot_dir.iterdir():
        f = sub / "SKILL.md"
        if f.is_file():
            return f
    return None


def _patcher_wrote_size(patcher_jsonl: Path, skill_name: str) -> int:
    """Largest 'Successfully wrote N characters to .../<skill_name>/SKILL.md' in iter N's patcher.jsonl."""
    if not patcher_jsonl.exists():
        return -1
    pat = re.compile(
        r"Successfully wrote (\d+) characters to "
        rf".*/{re.escape(skill_name)}/SKILL\.md"
    )
    sizes = []
    with patcher_jsonl.open() as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            content = ev.get("content", {})
            text = content.get("output") or content.get("text") or ""
            for m in pat.finditer(text):
                sizes.append(int(m.group(1)))
    return max(sizes) if sizes else -1


def _patcher_summary_text(patcher_jsonl: Path) -> str:
    """Extract the patcher's final agent-message text — its self-described patch."""
    if not patcher_jsonl.exists():
        return ""
    last_msg = ""
    with patcher_jsonl.open() as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("event") == "message" and ev.get("agent") == "Patcher":
                t = ev.get("content", {}).get("text", "")
                if t:
                    last_msg = t
    return last_msg


def _line_diff_deletions(pre_md: Path, post_md: Path, top_n: int = 3) -> list[str]:
    """Lines present in pre but not in post (substring after normalize). Top N by length (longer = more
    informative)."""
    if not pre_md.exists() or not post_md.exists():
        return []
    pre_lines = [ln.rstrip() for ln in pre_md.read_text(encoding="utf-8").splitlines()]
    post_lines = set(ln.rstrip() for ln in post_md.read_text(encoding="utf-8").splitlines())
    deleted = [ln for ln in pre_lines
               if ln.strip() and ln.strip() not in {p.strip() for p in post_lines}
               and not ln.strip().startswith("#")]
    deleted.sort(key=len, reverse=True)
    return deleted[:top_n]


def _provenance_search(rule_text: str, run_dir: Path,
                       upto_iter: int, skill_name: str) -> str:
    """Crude provenance: scan prior iter_M/patcher.jsonl trajectories for a
    message that quotes a similar rule. Return the iter_M batch task ids if
    found, else 'unknown'."""
    if not rule_text or len(rule_text.strip()) < 25:
        return "unknown"
    train_dir = run_dir / "train"
    needle = rule_text.strip()[:60].lower()
    for m in range(1, upto_iter):
        pj = train_dir / f"iter_{m}" / "patcher.jsonl"
        if not pj.exists():
            continue
        try:
            text = pj.read_text(encoding="utf-8", errors="replace").lower()
        except Exception:
            continue
        if needle in text:
            # Attach iter_M's batch from training_results
            return f"introduced_in_iter_{m}"
    return "unknown"


def _has_anti_wipe(run_dir: Path) -> bool:
    """True if this run was trained with the anti-wipe code-level guard.

    Heuristic by run-name (the only durable signal we have post-hoc):
      - any v8 run whose name contains "fix" or "oqa-gpt41-smoke"
        (the latter was the OfficeQA 4.1 smoke we ran 2026-06-20 with
        anti-wipe code in place)
      - any v8 run whose name contains "anti-wipe"
    All other runs (v6, tr-lite, v8 no-fix, SkillGrad) trained pre-fix
    or without the guard.
    """
    n = run_dir.name.lower()
    if "fix" in n:
        return True
    if "anti-wipe" in n:
        return True
    if n == "g2b-v8_gpt-4.1_oqa-gpt41-smoke":
        return True
    return False


def _scan_run(run_dir: Path, anti_wipe_assumed: bool) -> list[dict]:
    """Scan one run, return list of detected wipe events."""
    train_dir = run_dir / "train"
    if not train_dir.exists():
        return []
    tr_path = train_dir / "training_results.json"
    if not tr_path.exists():
        return []
    try:
        tr = json.loads(tr_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    skill_name = tr.get("skill_name", "xlsx")
    iters = tr.get("iterations", [])
    n_iter = len(iters)
    if n_iter < 2:
        return []

    # Build snapshot size table
    snapshots: dict[int, tuple[int, int, Path]] = {}  # iter → (bytes, lines, path)
    for i in range(1, n_iter + 2):
        snap_dir = train_dir / f"snapshot_iter_{i}"
        md = _find_skill_md(snap_dir)
        if md is None:
            continue
        b = md.stat().st_size
        ln = sum(1 for _ in md.open(encoding="utf-8"))
        snapshots[i] = (b, ln, md)

    events: list[dict] = []
    for n in range(1, n_iter + 1):
        if n not in snapshots:
            continue
        pre_b, pre_ln, pre_md = snapshots[n]
        if pre_b <= MIN_PRE_BYTES:
            continue

        # post-iter state = snapshot N+1 (start of next iter, after this iter's patch / revert)
        post = snapshots.get(n + 1)
        if post is None:
            continue
        post_b, post_ln, post_md = post

        wrote = _patcher_wrote_size(train_dir / f"iter_{n}" / "patcher.jsonl", skill_name)
        wipe_attempted = wrote > 0 and wrote < WIPE_THRESH_FRAC * pre_b
        wipe_survived = post_b < WIPE_THRESH_FRAC * pre_b

        if not (wipe_attempted or wipe_survived):
            continue

        # Stratum is determined by whether the run was trained with the
        # anti-wipe guard, NOT by whether the wipe happened to be reverted.
        # tr-lite, v6, v8-no-fix, SkillGrad runs may show "wipe attempted +
        # not-survived" by chance (e.g., the patcher's next iter rewrote
        # content) — that's NOT anti-wipe interception.
        run_has_aw = _has_anti_wipe(run_dir)
        if run_has_aw and wipe_attempted and not wipe_survived:
            stratum = "A"
            anti_wipe_engaged = "yes"
        elif wipe_survived and not run_has_aw:
            stratum = "B"
            anti_wipe_engaged = "no"
        elif wipe_survived and run_has_aw:
            # Anti-wipe in code but wipe still survived — bug or below
            # threshold. Tag for inspection.
            stratum = "A_failed"
            anti_wipe_engaged = "yes_but_failed"
        elif wipe_attempted and not run_has_aw:
            # No anti-wipe but wipe didn't survive (patcher rewrote next
            # iter). Not a Tier-0 event — skip.
            continue
        else:
            continue

        # Deletions
        if stratum == "A":
            # Reverted — actual file content reverted; record patcher-summary as
            # "what would have been deleted" proxy. Diff snap_N vs snap_(N+1)
            # will be ~empty.
            patcher_summary = _patcher_summary_text(
                train_dir / f"iter_{n}" / "patcher.jsonl"
            )[:800]
            deleted_rules = []
            deleted_note = (
                "(reverted) patcher final-message excerpt below; the actual "
                "wipe content was overwritten on disk."
            )
        else:
            patcher_summary = ""
            deleted_rules = _line_diff_deletions(pre_md, post_md, top_n=3)
            deleted_note = ""

        # Originating case id (best effort)
        deleted_with_provenance = []
        for rule in deleted_rules:
            origin = _provenance_search(rule, run_dir, n, skill_name)
            deleted_with_provenance.append({
                "rule": rule[:240],
                "originating_case_id_if_recoverable": origin,
            })

        # Next-iter context
        next_iter = iters[n] if n < n_iter else None
        prev_iter = iters[n - 1] if n - 1 < n_iter else None
        next_batch = next_iter.get("batch", []) if next_iter else []
        next_pre_correct = next_iter.get("pre_correct") if next_iter else None
        prev_pre_correct = prev_iter.get("pre_correct") if prev_iter else None
        delta = (
            (next_pre_correct - prev_pre_correct)
            if next_pre_correct is not None and prev_pre_correct is not None
            else None
        )

        events.append({
            "run_id": run_dir.name,
            "iter": n,
            "anti_wipe_engaged": anti_wipe_engaged,
            "stratum": stratum,
            "pre_lines": pre_ln,
            "post_lines": post_ln,
            "drop_pct": round((post_b - pre_b) / pre_b * 100.0, 1),
            "pre_size_bytes": pre_b,
            "post_size_bytes": post_b,
            "patcher_wrote_bytes": wrote,
            "wipe_attempted": wipe_attempted,
            "wipe_survived": wipe_survived,
            "deleted_rule_texts": deleted_with_provenance,
            "deleted_rules_note": deleted_note,
            "patcher_summary_excerpt": patcher_summary,
            "next_iter_batch_task_ids": next_batch,
            "prev_iter_pre_correct": prev_pre_correct,
            "next_iter_pre_correct": next_pre_correct,
            "next_iter_pass_count_delta": delta,
            "my_verdict": None,
            "verdict_notes": None,
        })

    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-root", default="results/runs")
    ap.add_argument("--output", default="analysis/rsm_tier0/events_auto.yaml")
    args = ap.parse_args()

    results_root = Path(args.results_root)
    runs = sorted(p for p in results_root.iterdir() if p.is_dir())

    all_events: list[dict] = []
    per_run_counts: dict[str, int] = {}
    for r in runs:
        anti_wipe_assumed = ("fix" in r.name.lower()
                             or "anti-wipe" in r.name.lower())
        events = _scan_run(r, anti_wipe_assumed)
        if events:
            per_run_counts[r.name] = len(events)
            all_events.extend(events)

    print(f"Scanned {len(runs)} runs; found {len(all_events)} wipe events:")
    for k, v in per_run_counts.items():
        print(f"  {k}: {v}")

    # Stratum tallies
    a_count = sum(1 for e in all_events if e["stratum"] == "A")
    b_count = sum(1 for e in all_events if e["stratum"] == "B")
    print(f"\nStratum A (anti-wipe engaged, intercepted): {a_count}")
    print(f"Stratum B (no anti-wipe, silent wipe):      {b_count}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"events": all_events, "summary": {
                "total": len(all_events),
                "stratum_A": a_count,
                "stratum_B": b_count,
                "per_run": per_run_counts,
            }},
            f, sort_keys=False, allow_unicode=True, width=120,
        )
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
