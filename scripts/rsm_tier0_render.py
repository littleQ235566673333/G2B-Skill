"""Render rsm_tier0 events_auto.yaml into a human-readable spot-check doc.

Output: analysis/rsm_tier0/events_spotcheck.md — one section per event,
with deleted-rule texts, batch-task-IDs context, and a verdict slot.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def render(events_path: Path, out_path: Path) -> None:
    d = yaml.safe_load(events_path.read_text(encoding="utf-8"))
    events = d["events"]
    summary = d["summary"]

    lines: list[str] = []
    lines.append("# RSM Tier 0 — spot-check sheet")
    lines.append("")
    lines.append(f"**Total events**: {summary['total']}")
    lines.append(f"**Stratum A** (anti-wipe engaged, intercepted): {summary['stratum_A']}")
    lines.append(f"**Stratum B** (no anti-wipe, silent wipe): {summary['stratum_B']}")
    lines.append("")
    lines.append("Per-event verdict goes in the YAML field `my_verdict` of "
                 "`events_filled.yaml`. Categories per template.md:")
    lines.append("- `destructive` — deleted content was useful")
    lines.append("- `stale_cleanup` — deleted content was redundant / stale; anti-wipe was over-protective")
    lines.append("- `ambiguous` — value unclear; default when in doubt")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Group by stratum
    for stratum_label in ["A", "B", "A_failed"]:
        rel = [e for e in events if e["stratum"] == stratum_label]
        if not rel:
            continue
        lines.append(f"## Stratum {stratum_label} ({len(rel)} events)")
        lines.append("")
        for i, e in enumerate(rel, 1):
            lines.append(f"### [{stratum_label}{i}] {e['run_id']} iter {e['iter']}")
            lines.append("")
            lines.append(f"- **anti_wipe_engaged**: {e['anti_wipe_engaged']}")
            lines.append(f"- **size change**: {e['pre_lines']} → {e['post_lines']} lines "
                         f"({e['drop_pct']:+.1f}%)")
            lines.append(f"- **patcher tried to write**: {e['patcher_wrote_bytes']} B "
                         f"(vs pre {e['pre_size_bytes']} B)")
            lines.append(f"- **wipe_attempted / wipe_survived**: "
                         f"{e['wipe_attempted']} / {e['wipe_survived']}")
            lines.append(f"- **prev / next pre_correct**: "
                         f"{e['prev_iter_pre_correct']} → {e['next_iter_pre_correct']} "
                         f"(Δ = {e['next_iter_pass_count_delta']})")
            lines.append(f"- **next_iter_batch**: {e['next_iter_batch_task_ids']}")
            lines.append("")

            if stratum_label == "A":
                # Reverted, content not directly diff-able. Show patcher's
                # self-summary as the proxy for "what was attempted".
                lines.append("**Patcher's self-summary excerpt** (would-be deleted/replaced):")
                lines.append("")
                lines.append("```")
                excerpt = e.get("patcher_summary_excerpt", "")[:1200]
                lines.append(excerpt or "(empty)")
                lines.append("```")
            else:
                lines.append("**Top-3 deleted rule lines** (line-level diff snap_N → snap_(N+1)):")
                lines.append("")
                for j, r in enumerate(e["deleted_rule_texts"], 1):
                    lines.append(f"{j}. ({r['originating_case_id_if_recoverable']}) "
                                 f"{r['rule']}")
                lines.append("")

            lines.append("**Verdict**: _ambiguous_ (provisional)")
            lines.append("")
            lines.append("**Notes**: _to fill_")
            lines.append("")
            lines.append("---")
            lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default="analysis/rsm_tier0/events_auto.yaml")
    ap.add_argument("--output", default="analysis/rsm_tier0/events_spotcheck.md")
    args = ap.parse_args()
    render(Path(args.events), Path(args.output))


if __name__ == "__main__":
    main()
