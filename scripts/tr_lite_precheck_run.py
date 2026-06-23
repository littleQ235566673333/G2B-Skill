"""TR-lite pre-check runner — analyze SS + WTQ traces and emit reports."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tr_lite_precheck_lib import patch_metrics


# ─────────────────────────────────────────────────────────────────────────
# Trace loaders
# ─────────────────────────────────────────────────────────────────────────

def load_snapshot(run_dir: Path, iter_n: int, skill_name: str) -> str | None:
    p = run_dir / "train" / f"snapshot_iter_{iter_n}" / skill_name / "SKILL.md"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def load_final_skill(run_dir: Path, skill_name: str) -> str | None:
    p = run_dir / "train" / "final_skill" / skill_name / "SKILL.md"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def extract_proposed_skill(run_dir: Path, iter_n: int, skill_name: str) -> str | None:
    """Last write_file call to SKILL.md in patcher.jsonl = patcher's proposed
    final state (before any anti-wipe revert)."""
    p = run_dir / "train" / f"iter_{iter_n}" / "patcher.jsonl"
    if not p.exists():
        return None
    last_content = None
    for line in p.read_text().splitlines():
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("event") != "tool_call":
            continue
        c = e.get("content", {})
        if c.get("tool") != "write_file":
            continue
        args = c.get("arguments", "")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                continue
        fp = args.get("file_path", "")
        content = args.get("content", "")
        if f"/{skill_name}/SKILL.md" in fp and "references/" not in fp:
            last_content = content
    return last_content


# ─────────────────────────────────────────────────────────────────────────
# Per-bench analysis
# ─────────────────────────────────────────────────────────────────────────

def analyze_run(run_id: str, skill_name: str, n_iters: int = 10) -> dict:
    """Build (S_old, S_new_accepted, S_new_proposed) triples for each iter
    and compute per-patch metrics for both Layer A and Layer B."""
    run_dir = Path("results/runs") / run_id
    layer_a_patches = []
    layer_b_patches = []
    proposed_available_count = 0

    for iter_n in range(1, n_iters + 1):
        s_old = load_snapshot(run_dir, iter_n, skill_name)
        # S_new_accepted is the snapshot at iter_{n+1}, except for last iter
        # where we use final_skill
        if iter_n < n_iters:
            s_new_accepted = load_snapshot(run_dir, iter_n + 1, skill_name)
        else:
            s_new_accepted = load_final_skill(run_dir, skill_name)
        s_new_proposed = extract_proposed_skill(run_dir, iter_n, skill_name)
        if s_old is None or s_new_accepted is None:
            continue

        a_metrics = patch_metrics(s_old, s_new_accepted)
        a_metrics["iter"] = iter_n
        layer_a_patches.append(a_metrics)

        if s_new_proposed is not None:
            proposed_available_count += 1
            b_metrics = patch_metrics(s_old, s_new_proposed)
            b_metrics["iter"] = iter_n
            b_metrics["proposed_size"] = len(s_new_proposed)
            b_metrics["accepted_size"] = len(s_new_accepted)
            b_metrics["was_reverted"] = abs(len(s_new_proposed) - len(s_new_accepted)) > 100
            layer_b_patches.append(b_metrics)

    return {
        "layer_a": layer_a_patches,
        "layer_b": layer_b_patches,
        "n_proposed": proposed_available_count,
    }


def aggregate(patches: list[dict]) -> dict:
    if not patches:
        return {}
    n = len(patches)
    return {
        "n_patches": n,
        "high_ratio_rate": sum(1 for p in patches if p["has_high_ratio_section"]) / n,
        "deleted_rate": sum(1 for p in patches if p["n_deleted"] > 0) / n,
        "added_rate": sum(1 for p in patches if p["n_added"] > 0) / n,
        "mean_max_ratio": sum(p["max_section_edit_ratio"] for p in patches) / n,
        "mean_avg_ratio": sum(p["mean_section_edit_ratio"] for p in patches) / n,
        "max_observed_ratio": max(p["max_section_edit_ratio"] for p in patches),
    }


def make_report(bench_label: str, run_id: str, skill_name: str) -> str:
    data = analyze_run(run_id, skill_name)
    a_agg = aggregate(data["layer_a"])
    b_agg = aggregate(data["layer_b"])

    lines = []
    lines.append(f"=== v8 + anti-wipe trace pre-check ({bench_label}) ===")
    lines.append(f"run_id: {run_id}")
    lines.append("")
    lines.append("Patch counts:")
    lines.append(f"  accepted patches:  {a_agg.get('n_patches', 0)}")
    lines.append(f"  proposed patches available: {data['n_proposed']}")
    lines.append("")
    lines.append("Layer A — accepted patch stats (S_old → S_new_accepted):")
    if a_agg:
        lines.append(f"  high_ratio_patch_rate (any section >0.5): {a_agg['high_ratio_rate']*100:.0f}%")
        lines.append(f"  deleted_section_patch_rate:              {a_agg['deleted_rate']*100:.0f}%")
        lines.append(f"  added_section_patch_rate:                {a_agg['added_rate']*100:.0f}%")
        lines.append(f"  mean of max_section_edit_ratio:          {a_agg['mean_max_ratio']:.3f}")
        lines.append(f"  mean of mean_section_edit_ratio:         {a_agg['mean_avg_ratio']:.3f}")
        lines.append(f"  max observed section edit ratio:         {a_agg['max_observed_ratio']:.3f}")
    lines.append("")
    lines.append("Layer B — proposed patch stats (S_old → S_new_proposed):")
    if b_agg:
        lines.append(f"  high_ratio_patch_rate (any section >0.5): {b_agg['high_ratio_rate']*100:.0f}%")
        lines.append(f"  deleted_section_patch_rate:              {b_agg['deleted_rate']*100:.0f}%")
        lines.append(f"  added_section_patch_rate:                {b_agg['added_rate']*100:.0f}%")
        lines.append(f"  mean of max_section_edit_ratio:          {b_agg['mean_max_ratio']:.3f}")
        lines.append(f"  mean of mean_section_edit_ratio:         {b_agg['mean_avg_ratio']:.3f}")
        lines.append(f"  max observed section edit ratio:         {b_agg['max_observed_ratio']:.3f}")
    else:
        lines.append("  N/A: S_new_proposed not in trace")
    lines.append("")

    # GO/NO-GO based on Layer A
    if a_agg:
        hr = a_agg["high_ratio_rate"]
        dr = a_agg["deleted_rate"]
        triggers = []
        if hr >= 0.20:
            triggers.append(f"high_ratio_rate {hr*100:.0f}% ≥ 20%")
        if dr >= 0.10:
            triggers.append(f"deleted_rate {dr*100:.0f}% ≥ 10%")
        decision = "GO" if triggers else "NO-GO"
        rationale = "; ".join(triggers) if triggers else \
            f"both below threshold (high_ratio_rate {hr*100:.0f}%, deleted_rate {dr*100:.0f}%)"
        lines.append("Go/No-go decision:")
        lines.append(f"  GO if (high_ratio_rate ≥ 20%) OR (deleted_rate ≥ 10%)")
        lines.append(f"  Decision: {decision}")
        lines.append(f"  Rationale: {rationale}")
    lines.append("")

    # Per-iter table for transparency
    lines.append("Per-iter Layer A details:")
    lines.append(f"  {'iter':>4} | {'n_old':>5} {'n_new':>5} | {'matched':>7} {'del':>3} {'add':>3} | {'max_ratio':>9} {'mean_ratio':>10}")
    for p in data["layer_a"]:
        lines.append(f"  {p['iter']:>4} | {p['n_old_sections']:>5} {p['n_new_sections']:>5} | "
                     f"{p['n_matched']:>7} {p['n_deleted']:>3} {p['n_added']:>3} | "
                     f"{p['max_section_edit_ratio']:>9.3f} {p['mean_section_edit_ratio']:>10.3f}"
                     f"{'  *high' if p['has_high_ratio_section'] else ''}")
    lines.append("")

    if data["layer_b"]:
        lines.append("Per-iter Layer B details (proposed before anti-wipe revert):")
        lines.append(f"  {'iter':>4} | {'prop B':>7} {'acc B':>7} {'reverted':>9} | {'max_ratio':>9}")
        for p in data["layer_b"]:
            lines.append(f"  {p['iter']:>4} | {p['proposed_size']:>7} {p['accepted_size']:>7} "
                         f"{'YES' if p['was_reverted'] else '':>9} | {p['max_section_edit_ratio']:>9.3f}"
                         f"{'  *high' if p['has_high_ratio_section'] else ''}")
    return "\n".join(lines)


if __name__ == "__main__":
    out_dir = Path("analysis")
    out_dir.mkdir(exist_ok=True)

    decisions = {}
    for label, run_id, skill in [
        ("SS GPT-4.1", "g2b-v8_gpt-4.1_ss-gpt41-fix", "xlsx"),
        ("WTQ GPT-4.1", "g2b-v8_gpt-4.1_wtq-gpt41-fix", "wtq"),
    ]:
        report = make_report(label, run_id, skill)
        out_path = out_dir / f"tr_lite_precheck_{run_id}.md"
        out_path.write_text(report, encoding="utf-8")
        print(report)
        print()
        # Extract decision
        for line in report.split("\n"):
            if line.strip().startswith("Decision:"):
                decisions[label] = line.split(":")[1].strip()

    # Final joint
    print("="*60)
    print("FINAL JOINT DECISION")
    print("="*60)
    for k, v in decisions.items():
        print(f"  {k}: {v}")
    go_set = {k for k, v in decisions.items() if v == "GO"}
    if len(go_set) == 2:
        print("\nBoth benches GO → implement TR-lite, run main experiment ($40)")
    elif len(go_set) == 1:
        print(f"\nOnly {next(iter(go_set))} GO → implement TR-lite, but run only on that bench")
    else:
        print("\nBoth benches NO-GO → STOP TR-lite, paper uses anti-wipe guard layer only")
