"""v7 helpers — group evidence builder + primary trajectory picker.

Used by v7 training/smoke scripts to convert K-rollout group results into:
  1. A "primary" assessment per task that SkillGrad's classify/diagnose can use
  2. A group_evidence.md file injected into SkillGrad's patcher input

Design: SkillGrad's downstream (classify, diagnose, momentum, patch) is
unchanged. v7 is purely additive at two points: (a) EXECUTE becomes K-rollout,
(b) PATCH receives an extra group_evidence_path.
"""
from __future__ import annotations
from pathlib import Path


def pick_primary_assessment(group_assessments: list[dict]) -> dict:
    """Pick one assessment per task to feed into SkillGrad's classify/diagnose.

    For mixed groups, prefer a FAILED rollout so the diagnoser analyzes a
    failure trace (richer signal). For all_pass / all_fail, take rollout 0.
    """
    if not group_assessments:
        raise ValueError("empty group_assessments")
    n_succ = sum(1 for a in group_assessments if a["is_correct"])
    n = len(group_assessments)
    if 0 < n_succ < n:
        for a in group_assessments:
            if not a["is_correct"]:
                return a
    return group_assessments[0]


def build_group_evidence_md(
    per_task_groups: list[tuple[str, list[dict]]],
    iter_num: int,
    iter_dir: Path,
) -> Path:
    """Write group_evidence.md describing per-task K-rollout outcomes.

    Args:
        per_task_groups: list of (task_id, list_of_K_assessments)
        iter_num: 1-indexed iteration
        iter_dir: where to write the file

    Returns: path to the written file.
    """
    lines = [f"# K-rollout group evidence (iter {iter_num})\n"]
    lines.append(
        "Each task in this batch was rolled out K times under the SAME skill "
        "artifact. The diagnoses you also see were generated from the primary "
        "rollout (a failed one when the group is mixed). Use the per-rollout "
        "outcomes below as same-skill same-task contrastive evidence in "
        "addition to the diagnoses.\n"
    )
    lines.append("## Summary\n")
    lines.append("| task | K | n_succ | group_type | cell range |")
    lines.append("|---|---|---|---|---|")
    for tid, group in per_task_groups:
        K = len(group)
        n_succ = sum(1 for a in group if a["is_correct"])
        if n_succ == K:
            gt = "all_success"
        elif n_succ == 0:
            gt = "all_fail"
        else:
            gt = "mixed"
        cells = [a["accuracy"]["accuracy"] for a in group]
        cell_range = f"{min(cells):.0%}–{max(cells):.0%}"
        lines.append(f"| {tid} | {K} | {n_succ} | {gt} | {cell_range} |")
    lines.append("")

    lines.append("## Per-task rollout details\n")
    for tid, group in per_task_groups:
        lines.append(f"### Task {tid}")
        for a in sorted(group, key=lambda x: x.get("_rollout_idx", 0)):
            r = a.get("_rollout_idx", "?")
            verdict = "PASS" if a["is_correct"] else "FAIL"
            cell = a["accuracy"]["accuracy"]
            traj = a.get("trajectory_path", "")
            lines.append(
                f"- rollout r{r}: **{verdict}**, cell {cell:.0%}"
                + (f" — trajectory: `{traj}`" if traj else "")
            )
        lines.append("")

    out = iter_dir / "group_evidence.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
