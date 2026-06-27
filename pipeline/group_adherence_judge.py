"""SAPR-minimal: per-rule adherence judge stage.

Inserted between GROUP-EXECUTE and GROUP-DIAGNOSE in g2b_training.

For each (rollout, L2-rule) pair, an LLM judge produces:
  - applicable: did this rule apply to this task
  - adhered: did the rollout follow the rule (0.0-1.0)

Outputs adherence_summary.md consumed by group_patcher prompt
(generic, no rule-hardcoding per pre-reg).
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev

from agents import Agent, Runner

from pipeline.helpers import _resolve_model
from runners.cost_tracker import CostTracker
from runners.model_settings import get_model_settings


def extract_l2_rules(skill_md_path: Path) -> list[dict]:
    """Extract L2 sections (## headings) as judgeable rules.

    Returns list of {rule_id, heading, summary} dicts. Skips
    'Common Pitfalls' section and the YAML frontmatter.
    """
    if not skill_md_path.exists():
        return []
    text = skill_md_path.read_text(encoding="utf-8")
    body = re.sub(r"^---.*?\n---\n", "", text, count=1, flags=re.S)
    sections = re.split(r"^## ", body, flags=re.M)
    rules = []
    idx = 0
    for sec in sections[1:]:
        heading_line, _, rest = sec.partition("\n")
        heading = heading_line.strip()
        if "common pitfalls" in heading.lower():
            continue
        idx += 1
        rule_id = f"R{idx}_" + re.sub(r"[^a-zA-Z]+", "_", heading.lower())[:30].strip("_")
        summary = rest.strip().split("\n\n", 1)[0][:400]
        rules.append({"rule_id": rule_id, "heading": heading, "summary": summary})
    return rules


# Tuning 3: rule-age tracking — read birth iter from snapshot history
def _rule_birth_iters(skill_dir: Path, current_iter: int) -> dict[str, int]:
    """For each rule heading, find earliest iter it appeared in.

    Walks snapshot_iter_1 .. snapshot_iter_{current_iter} and records
    iter index when each heading first appears. Returns {heading: birth_iter}.

    skill_dir layout: <run_dir>/skills/xlsx/
    train dir is at:  <run_dir>/train/
    So we need skill_dir.parent.parent / "train" not skill_dir.parent / "train".
    """
    birth = {}
    train_dir = skill_dir.parent.parent / "train"
    if not train_dir.exists():
        return birth
    for i in range(1, current_iter + 1):
        snap_skill = train_dir / f"snapshot_iter_{i}" / "xlsx" / "SKILL.md"
        if not snap_skill.exists():
            continue
        try:
            text = snap_skill.read_text(encoding="utf-8")
            for line in text.split("\n"):
                if line.startswith("## "):
                    h = line[3:].strip()
                    if "common pitfalls" in h.lower():
                        continue
                    if h not in birth:
                        birth[h] = i
        except Exception:
            continue
    return birth


JUDGE_PROMPT = """You evaluate whether an agent's execution trace adhered to a specific rule from its skill.

RULE HEADING: {heading}
RULE SUMMARY: {summary}

EXECUTION TRACE (truncated):
{trace}

Output JSON only:
{{
  "applicable": <true|false>,
  "adhered": <0.0-1.0 if applicable, else null>,
  "evidence": "<one sentence>"
}}"""


async def _judge_one(
    trace: str, rule: dict, model: str, cost_tracker: CostTracker,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Single (rollout, rule) → adherence verdict."""
    prompt = JUDGE_PROMPT.format(
        heading=rule["heading"],
        summary=rule["summary"],
        trace=trace[:6000],
    )
    async with semaphore:
        agent = Agent(
            name="AdherenceJudge",
            instructions="You are a strict adherence judge. Output JSON only.",
            model=_resolve_model(model),
            model_settings=get_model_settings(model),
        )
        try:
            result = Runner.run_streamed(agent, prompt, max_turns=2)
            async for _ in result.stream_events():
                pass
            output = result.final_output or ""
            cost_tracker.update(result)
        except Exception as e:
            return {"rule_id": rule["rule_id"], "ok": False, "error": str(e)[:120]}

    text = output.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        parsed = json.loads(text)
        return {
            "rule_id": rule["rule_id"],
            "applicable": parsed.get("applicable"),
            "adhered": parsed.get("adhered"),
            "evidence": str(parsed.get("evidence", ""))[:200],
            "ok": True,
        }
    except Exception as e:
        return {"rule_id": rule["rule_id"], "ok": False, "error": f"parse:{e}"[:120]}


async def run_group_adherence_judge(
    groups: list[dict],
    skill_md_path: Path,
    model: str,
    iter_dir: Path,
    cost_tracker: CostTracker,
    semaphore: asyncio.Semaphore,
) -> Path:
    """Run adherence judge on K rollouts × |L2 rules| for the batch.

    `groups` is the list of group dicts from group_execution. Each group
    has assessments[] with trace text and outcome correctness.

    Writes adherence_summary.md (consumed by patcher prompt) and
    adherence_raw.jsonl. Returns path to summary.
    """
    rules = extract_l2_rules(skill_md_path)
    summary_path = iter_dir / "adherence_summary.md"
    raw_path = iter_dir / "adherence_raw.jsonl"

    if not rules:
        summary_path.write_text("# Adherence summary\n\n_no L2 rules extracted_\n")
        return summary_path

    # Tuning 3: rule-age filter — skip rules added by patcher < 2 iter ago
    # Seed rules (present in snapshot_iter_1) are NEVER filtered — they're
    # the foundation, not new additions. Only rules added by patcher in
    # iter ≥ 2 are subject to age filter.
    try:
        current_iter = int(iter_dir.name.replace("iter_", ""))
    except Exception:
        current_iter = 1
    skill_dir = skill_md_path.parent
    birth = _rule_birth_iters(skill_dir, current_iter)
    pre_filter_count = len(rules)
    rules = [
        r for r in rules
        # Keep rule if: it's a seed rule (birth=1) OR it's been around ≥ 2 iter
        if birth.get(r["heading"], current_iter) == 1
        or birth.get(r["heading"], current_iter) <= current_iter - 2
    ]
    filtered_count = pre_filter_count - len(rules)
    if filtered_count > 0:
        print(f"  [SAPR-T3] rule-age filter: skipped {filtered_count}/{pre_filter_count} new rules (<2 iter old, non-seed)")

    if not rules:
        summary_path.write_text("# Adherence summary\n\n_all rules younger than 2 iter; T3 filter caught all_\n")
        return summary_path

    # Collect (trace, outcome, group_type) per rollout
    items = []
    for g in groups:
        for asmt in g.get("assessments", []):
            trace = asmt.get("execution_trace") or asmt.get("executor_output") or ""
            outcome = bool(asmt.get("is_correct"))
            tid = asmt.get("id") or asmt.get("task_id") or "?"
            items.append({"trace": trace, "outcome": outcome, "task_id": tid})

    # Spawn judge calls in parallel
    tasks = []
    for it in items:
        for rule in rules:
            tasks.append(
                _judge_one(it["trace"], rule, model, cost_tracker, semaphore)
            )
    results = await asyncio.gather(*tasks)

    # Re-attach (task_id, outcome) by reconstructing index
    raw = []
    idx = 0
    for it in items:
        for rule in rules:
            r = results[idx]
            r["task_id"] = it["task_id"]
            r["outcome_correct"] = it["outcome"]
            raw.append(r)
            idx += 1

    with open(raw_path, "w") as f:
        for r in raw:
            f.write(json.dumps(r) + "\n")

    summary_md = _render_adherence_summary(raw, rules)
    summary_path.write_text(summary_md)
    return summary_path


def _render_adherence_summary(raw: list[dict], rules: list[dict]) -> str:
    """Render adherence summary md for patcher consumption.

    Generic format (no rule-specific hardcoding):
      - per-rule mean adherence on FAIL rollouts vs PASS rollouts
      - flag rules with low adherence-on-fail (clarity/prominence issue)
      - flag rules with high adherence-on-fail (content issue)
    """
    lines = ["# Adherence signal (per-rule, this batch)\n"]
    lines.append(
        "From the K-rollout group dispatch, the adherence judge "
        "scored each rollout × L2-rule pair. Two patterns are "
        "surfaced for the patcher:\n"
    )
    lines.append(
        "- **Low adherence on fail**: rule was systematically NOT "
        "followed by failed rollouts. The rule's expression may be "
        "unclear or low-prominence. **Prefer rewriting prominence / "
        "wording / position, NOT content.**\n"
    )
    lines.append(
        "- **High adherence on fail**: rule was followed but outcome "
        "still failed. The rule's content may be wrong. **Prefer "
        "rewriting content / decision logic, NOT prominence.**\n"
    )
    lines.append("\n## Per-rule statistics\n")
    lines.append("| Rule | Heading | n_pass | adh_pass | n_fail | adh_fail | flag |")
    lines.append("|------|---------|--------|----------|--------|----------|------|")

    by_rule = {}
    for r in raw:
        if not r.get("ok") or r.get("applicable") is False:
            continue
        adh = r.get("adhered")
        if adh is None or not isinstance(adh, (int, float)):
            continue
        rid = r["rule_id"]
        by_rule.setdefault(rid, {"pass": [], "fail": []})
        bucket = "pass" if r.get("outcome_correct") else "fail"
        by_rule[rid][bucket].append(float(adh))

    for rule in rules:
        rid = rule["rule_id"]
        d = by_rule.get(rid, {"pass": [], "fail": []})
        n_pass, n_fail = len(d["pass"]), len(d["fail"])
        adh_pass = mean(d["pass"]) if d["pass"] else None
        adh_fail = mean(d["fail"]) if d["fail"] else None
        flag = ""
        if n_fail >= 2 and adh_fail is not None:
            if adh_fail < 0.4:
                flag = "LOW_ADH_ON_FAIL → rewrite prominence/wording"
            elif adh_fail >= 0.7 and (adh_pass is None or adh_pass >= adh_fail):
                flag = "HIGH_ADH_ON_FAIL → rewrite content"
        adh_pass_str = f"{adh_pass:.2f}" if adh_pass is not None else "—"
        adh_fail_str = f"{adh_fail:.2f}" if adh_fail is not None else "—"
        lines.append(
            f"| {rid} | {rule['heading'][:35]} | {n_pass} | "
            f"{adh_pass_str} | {n_fail} | {adh_fail_str} | {flag} |"
        )
    return "\n".join(lines) + "\n"



