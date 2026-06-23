"""Group diagnoser runner (Phase 2 — three-branch dispatch over a K-rollout group).

For each group, classify the group via ``classify_group(...)``, build a
branch-specific query, dispatch to the matching system prompt, parse
the LLM's ``<card>...</card>`` YAML output, validate the schema
constraints, and persist the card. The runner is bench-agnostic — it
operates on assessment dicts produced by ``bench.assess(...)``.

Design notes
------------
- Three branches: mixed / all_fail / all_success — see
  ``prompts/group_diagnoser.py`` for the prompts.
- Output: per-group ``group_<task_id>_card.md`` plus a batch-level
  ``batch_diagnostic_cards.md`` (consumed by Phase 3 momentum).
- Schema enforcement: post-parse validators reject claim lists that
  violate hard constraints (all_fail emits non-low evidence; all_success
  emits non-empty claims).

Public API
----------
- run_group_diagnose(group_assessments, group_type, ..., iter_dir, ...) -> dict
- assemble_group_cards(cards, output_path) -> Path
"""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Optional

import yaml
from agents import Agent, Runner

from pipeline.execution import _write_workspace
from pipeline.group_execution import group_advantage, group_summary
from pipeline.helpers import _build_file_tools, _resolve_model
from prompts.group_diagnoser import (
    ALL_FAIL_DIAGNOSER_PROMPT,
    ALL_SUCCESS_DIAGNOSER_PROMPT,
    MIXED_DIAGNOSER_PROMPT,
)
from runners.cost_tracker import CostTracker
from runners.model_settings import get_model_settings
from runners.trajectory_logger import (
    TrajectoryLogger,
    save_merged_trace,
    stream_with_logging,
)


# ═══════════════════════════════════════════════════════════════════════════
# Per-branch query builders
# ═══════════════════════════════════════════════════════════════════════════

def _build_advantage_table(group_assessments: list[dict]) -> str:
    """Render a per-rollout reward+advantage table for the prompt context."""
    advs = group_advantage(group_assessments, reward_key="soft")
    lines = ["| rollout | is_correct | soft_acc | advantage |",
             "|---------|------------|----------|-----------|"]
    for k, (a, adv) in enumerate(zip(group_assessments, advs)):
        lines.append(
            f"| r{k} | {a['is_correct']} | "
            f"{a['accuracy']['accuracy']:.2f} | {adv:+.2f} |"
        )
    return "\n".join(lines)


def _ensure_merged_traces(group_assessments: list[dict]) -> list[Path]:
    """Build merged trace.jsonl files from the raw exec_r<k>.jsonl logs.

    Returns paths in rollout order so the prompt can list them.
    """
    paths: list[Path] = []
    for k, a in enumerate(group_assessments):
        task_workdir = Path(a["task_workdir"])
        raw = task_workdir / f"exec_r{k}.jsonl"
        if not raw.exists():
            # group_execution writes per-rollout exec_r0.jsonl in the
            # rollout subdir; fall back to that.
            raw = task_workdir / "exec_r0.jsonl"
        merged = task_workdir / "trace.jsonl"
        if raw.exists() and not merged.exists():
            try:
                save_merged_trace(raw, merged)
            except Exception:
                pass
        paths.append(merged if merged.exists() else raw)
    return paths


def _build_mixed_query(
    group_assessments: list[dict], task_str: str, iter_id: str,
) -> str:
    """Query for the mixed branch — ranks rollouts high/low by advantage."""
    advs = group_advantage(group_assessments, reward_key="soft")
    summary = group_summary(group_assessments)
    traces = _ensure_merged_traces(group_assessments)

    high_idx = [k for k, adv in enumerate(advs) if adv > 0]
    low_idx = [k for k, adv in enumerate(advs) if adv <= 0]

    cell_comp_lines = []
    for k, a in enumerate(group_assessments):
        if not a["is_correct"]:
            cell_comp_lines.append(
                f"### r{k} cell comparison\n{a.get('cell_comparison', '(n/a)')}\n"
            )

    return (
        f"## Task\n{task_str}\n\n"
        f"## Group reward distribution (iter={iter_id})\n"
        f"K={summary['K']}, n_success={summary['n_success']}, "
        f"n_fail={summary['n_fail']}, "
        f"soft_range={summary['soft_acc_range']:.2f}\n\n"
        f"{_build_advantage_table(group_assessments)}\n\n"
        f"## High-advantage rollouts: {high_idx}\n"
        f"## Low-advantage rollouts:  {low_idx}\n\n"
        f"## Per-rollout trajectories (read with read_file)\n"
        + "\n".join(f"- r{k}: {p}" for k, p in enumerate(traces))
        + "\n\n"
        f"## Failure cell-comparisons\n"
        + ("\n".join(cell_comp_lines) if cell_comp_lines else "(none)\n")
    )


def _build_all_fail_query(
    group_assessments: list[dict], task_str: str, iter_id: str,
) -> str:
    """Query for the all_fail branch — aggregate K failure trajectories."""
    summary = group_summary(group_assessments)
    traces = _ensure_merged_traces(group_assessments)

    cell_comps = "\n".join(
        f"### r{k} cell comparison\n{a.get('cell_comparison', '(n/a)')}\n"
        for k, a in enumerate(group_assessments)
    )

    return (
        f"## Task\n{task_str}\n\n"
        f"## Group reward distribution (iter={iter_id})\n"
        f"K={summary['K']}, all rollouts failed. "
        f"soft_acc range: [{summary['soft_acc_min']:.2f}, "
        f"{summary['soft_acc_max']:.2f}]\n\n"
        f"{_build_advantage_table(group_assessments)}\n\n"
        f"## Per-rollout trajectories (read with read_file)\n"
        + "\n".join(f"- r{k}: {p}" for k, p in enumerate(traces))
        + "\n\n"
        f"## Per-rollout cell comparisons\n{cell_comps}\n"
    )


def _build_all_success_query(
    group_assessments: list[dict], task_str: str, iter_id: str,
    skill_dir: Path,
) -> str:
    """Query for the all_success branch — extract regression anchor."""
    summary = group_summary(group_assessments)
    traces = _ensure_merged_traces(group_assessments)

    return (
        f"## Task\n{task_str}\n\n"
        f"## Group reward distribution (iter={iter_id})\n"
        f"K={summary['K']}, all {summary['n_success']} rollouts succeeded.\n\n"
        f"{_build_advantage_table(group_assessments)}\n\n"
        f"## Per-rollout trajectories (read with read_file)\n"
        + "\n".join(f"- r{k}: {p}" for k, p in enumerate(traces))
        + "\n\n"
        f"## Current skill directory (read for covered_anchors attribution)\n"
        f"- {skill_dir}\n"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Card extraction + validation
# ═══════════════════════════════════════════════════════════════════════════

_CARD_RE = re.compile(r"<card>(.*?)</card>", re.DOTALL)


def _extract_card_yaml(agent_output: str) -> dict | None:
    """Pull the first <card>...</card> block, parse as YAML.

    Returns the parsed dict, or None if no parseable card.
    """
    m = _CARD_RE.search(agent_output)
    if not m:
        return None
    body = m.group(1).strip()
    try:
        return yaml.safe_load(body)
    except yaml.YAMLError:
        return None


def _validate_card(card: dict, expected_group_type: str) -> tuple[bool, list[str]]:
    """Apply Phase 2 hard constraints. Returns (ok, list_of_violations).

    Violations are messages we want logged + visible in the assembled
    cards file; we don't reject the card outright, but downstream
    consumers should treat violation-flagged cards with care.
    """
    violations: list[str] = []
    if not isinstance(card, dict):
        return False, ["card is not a dict"]
    if card.get("group_type") != expected_group_type:
        violations.append(
            f"group_type mismatch: card={card.get('group_type')!r} "
            f"expected={expected_group_type!r}"
        )
    claims = card.get("candidate_claims") or []
    # Fix S (NEW 2026-06-22): all_success branch may emit at most ONE
    # candidate_claim of kind=procedural_template. Empty list still valid.
    if expected_group_type == "all_success":
        if len(claims) > 1:
            violations.append(
                f"all_success branch may have at most 1 candidate_claim "
                f"(kind=procedural_template); got {len(claims)}"
            )
        for c in claims:
            if c.get("kind") != "procedural_template":
                violations.append(
                    f"all_success claim {c.get('id', '?')!r} has "
                    f"kind={c.get('kind')!r}; only 'procedural_template' "
                    f"allowed in this branch"
                )
                continue
            # Required fields for procedural_template
            for fld in ("technique_name", "applies_when",
                        "procedure_prose", "why_it_worked"):
                v = (c.get(fld) or "").strip() if isinstance(c.get(fld), str) else ""
                if not v:
                    violations.append(
                        f"all_success procedural_template claim "
                        f"{c.get('id', '?')!r} missing/empty field {fld!r}"
                    )
            # technique_name should be kebab-case slug, ≤ 60 chars
            tn = c.get("technique_name", "")
            if isinstance(tn, str):
                if not re.fullmatch(r"[a-z0-9-]+", tn or "_dummy_"):
                    violations.append(
                        f"all_success procedural_template claim "
                        f"{c.get('id', '?')!r} technique_name {tn!r} "
                        f"not kebab-case (lowercase + digits + hyphen only)"
                    )
                if len(tn) > 60:
                    violations.append(
                        f"all_success procedural_template claim "
                        f"{c.get('id', '?')!r} technique_name > 60 chars"
                    )
            # applies_when must be ≤ 30 words, no task literals
            aw = (c.get("applies_when") or "").strip()
            if aw:
                if len(aw.split()) > 35:
                    violations.append(
                        f"all_success procedural_template claim "
                        f"{c.get('id', '?')!r} applies_when > 35 words; "
                        f"must be generic and concise"
                    )
                if re.search(r"\b\d{4,}\b", aw):
                    violations.append(
                        f"all_success procedural_template claim "
                        f"{c.get('id', '?')!r} applies_when contains "
                        f"4+ digit number (likely task literal)"
                    )
                if re.search(r"\.(xlsx|csv|txt|pdf)\b", aw, re.I):
                    violations.append(
                        f"all_success procedural_template claim "
                        f"{c.get('id', '?')!r} applies_when contains "
                        f"file extension; must be generic"
                    )
            # procedure_prose ≥ 15 tokens (substantive)
            pp = (c.get("procedure_prose") or "").strip()
            if pp and len(pp.split()) < 15:
                violations.append(
                    f"all_success procedural_template claim "
                    f"{c.get('id', '?')!r} procedure_prose < 15 tokens; "
                    f"must be substantive enough for L3 chapter rendering"
                )
    if expected_group_type == "all_success" and not card.get("regression_anchor"):
        violations.append("all_success branch must set regression_anchor=true")
    if expected_group_type == "all_fail":
        # Each card must declare convergence_label (NEW required field)
        conv = card.get("convergence_label")
        if conv not in ("CONVERGENT", "DIVERGENT"):
            violations.append(
                f"all_fail card missing or invalid convergence_label: "
                f"{conv!r}; must be 'CONVERGENT' or 'DIVERGENT'"
            )
        n_function_negative = 0
        for c in claims:
            kind = c.get("kind")
            estr = c.get("evidence_strength")
            if estr == "high":
                violations.append(
                    f"all_fail claim {c.get('id', '?')!r} has "
                    f"evidence_strength='high'; high is reserved for mixed branch"
                )
            elif kind == "function_negative":
                # function_negative may be emitted at low or medium strength.
                # REQUIRES card-level convergence_label=CONVERGENT.
                if estr not in ("low", "medium"):
                    violations.append(
                        f"all_fail claim {c.get('id', '?')!r} kind="
                        f"function_negative has invalid evidence_strength="
                        f"{estr!r}; must be 'low' or 'medium'"
                    )
                if conv != "CONVERGENT":
                    violations.append(
                        f"all_fail claim {c.get('id', '?')!r} kind="
                        f"function_negative requires card-level "
                        f"convergence_label='CONVERGENT', got {conv!r}"
                    )
                neg = c.get("negative_only_text") or {}
                for sub in ("applies_when", "avoid", "use_instead"):
                    val = (neg.get(sub) or "").strip()
                    if not val:
                        violations.append(
                            f"all_fail claim {c.get('id', '?')!r} kind="
                            f"function_negative missing negative_only_text.{sub}"
                        )
                # Literal-content check on applies_when (deterministic):
                aw = (neg.get("applies_when") or "").strip()
                if aw:
                    if re.search(r"\b\d{4,}\b", aw):
                        violations.append(
                            f"all_fail claim {c.get('id', '?')!r} applies_when "
                            f"contains 4+ digit number (likely task literal); "
                            f"applies_when must be generic"
                        )
                    if re.search(r"\b(oqa|nt)-\d+\b", aw, re.I):
                        violations.append(
                            f"all_fail claim {c.get('id', '?')!r} applies_when "
                            f"contains task-id pattern; must be generic"
                        )
                    if re.search(r"\.(xlsx|csv|txt|pdf)\b", aw, re.I):
                        violations.append(
                            f"all_fail claim {c.get('id', '?')!r} applies_when "
                            f"contains file extension; must be generic"
                        )
                    # NEW v2 specificity check: applies_when must contain at
                    # least one CONCRETE anchor that narrows scope, otherwise
                    # the rule will over-apply at executor time. Concrete
                    # anchors include:
                    #   - a column letter reference (e.g., "column A", "col B")
                    #   - a quoted header/sheet/value ("Total", 'Net')
                    #   - a spreadsheet function name (UPPERCASE: SUM, VLOOKUP,
                    #     INDEX, MATCH, IF, TEXT, COUNTIF, ...)
                    #   - a 'row N' pattern with numeric anchor
                    #   - a specific data-shape phrase ('paired columns',
                    #     'header row', 'multi-column', 'subset', etc. — NOT
                    #     'output sheet', 'destination', 'spreadsheet' alone)
                    has_col_letter = bool(re.search(r"\bcol(?:umn)?\s+[A-Z]\b", aw))
                    has_quoted = bool(re.search(r'["“‘][^"”’]{2,}["”’]', aw)) or bool(re.search(r"'[^']{2,}'", aw))
                    has_function = bool(re.search(
                        r"\b(SUM|SUMIF|VLOOKUP|HLOOKUP|XLOOKUP|INDEX|MATCH|IF|"
                        r"COUNTIF|COUNTIFS|SUMIFS|TEXT|DATE|YEAR|MONTH|DAY|"
                        r"CONCAT|CONCATENATE|LEFT|RIGHT|MID|LEN|TRIM|"
                        r"UPPER|LOWER|PROPER|FIND|SEARCH|REPLACE|SUBSTITUTE|"
                        r"ROUND|MOD|ABS|MAX|MIN|AVERAGE|FILTER|SORT|UNIQUE|"
                        r"OFFSET|INDIRECT|ADDRESS|ROW|COLUMN|TRANSPOSE|"
                        r"PIVOT|GROUPBY|MERGE|JOIN|HEADER|TEXTJOIN)\b", aw))
                    has_row_n = bool(re.search(r"\brow\s+\d+\b", aw, re.I))
                    # Generic openers that are HALLMARK of over-broad rules:
                    starts_generic = bool(re.match(
                        r"\s*(any task|all tasks?|when output|output sheet|"
                        r"destination|spreadsheet)", aw, re.I))
                    has_concrete = has_col_letter or has_quoted or has_function or has_row_n
                    if starts_generic and not has_concrete:
                        violations.append(
                            f"all_fail claim {c.get('id', '?')!r} applies_when "
                            f"opens with generic phrase ({aw[:40]!r}) and lacks "
                            f"a concrete anchor (column letter, quoted name, "
                            f"function name, or 'row N'); must narrow scope"
                        )
                # use_instead substantive content check (>= 10 tokens)
                ui = (neg.get("use_instead") or "").strip()
                if ui and len(ui.split()) < 10:
                    violations.append(
                        f"all_fail claim {c.get('id', '?')!r} use_instead "
                        f"is < 10 tokens; must contain substantive alternative"
                    )
                n_function_negative += 1
            elif estr == "medium":
                # medium without kind=function_negative is invalid for all_fail
                violations.append(
                    f"all_fail claim {c.get('id', '?')!r} has "
                    f"evidence_strength='medium' but kind={kind!r}; "
                    f"medium on all_fail requires kind='function_negative'"
                )
            elif estr != "low":
                violations.append(
                    f"all_fail claim {c.get('id', '?')!r} has invalid "
                    f"evidence_strength={estr!r}; must be 'low' or 'medium'"
                )
        if n_function_negative > 1:
            violations.append(
                f"all_fail card emitted {n_function_negative} kind="
                f"function_negative claims; max 1 per card"
            )
    if expected_group_type == "mixed":
        # Fix T (2026-06-22): mixed claims may be either contrastive (with
        # evidence_strength + advantage_split) OR procedural_template
        # (no strength/split). Validate each kind separately.
        n_pt_in_mixed = 0
        for c in claims:
            kind = c.get("kind")
            if kind == "procedural_template":
                n_pt_in_mixed += 1
                # Required fields for procedural_template (same as all_success)
                for fld in ("technique_name", "applies_when",
                            "procedure_prose", "why_it_worked"):
                    v = (c.get(fld) or "").strip() if isinstance(c.get(fld), str) else ""
                    if not v:
                        violations.append(
                            f"mixed procedural_template claim "
                            f"{c.get('id', '?')!r} missing/empty field {fld!r}"
                        )
                tn = c.get("technique_name", "")
                if isinstance(tn, str) and tn:
                    if not re.fullmatch(r"[a-z0-9-]+", tn):
                        violations.append(
                            f"mixed procedural_template claim "
                            f"{c.get('id', '?')!r} technique_name {tn!r} "
                            f"not kebab-case"
                        )
                aw = (c.get("applies_when") or "").strip()
                if aw and len(aw.split()) > 35:
                    violations.append(
                        f"mixed procedural_template claim "
                        f"{c.get('id', '?')!r} applies_when > 35 words"
                    )
            else:
                # Regular contrastive claim
                if c.get("evidence_strength") not in ("high", "medium"):
                    violations.append(
                        f"mixed claim {c.get('id', '?')!r} has "
                        f"evidence_strength={c.get('evidence_strength')!r}; "
                        f"must be 'high' or 'medium'"
                    )
        if n_pt_in_mixed > 1:
            violations.append(
                f"mixed branch may have at most 1 procedural_template "
                f"claim; got {n_pt_in_mixed}"
            )
    return (len(violations) == 0), violations


# ═══════════════════════════════════════════════════════════════════════════
# Per-branch async runners
# ═══════════════════════════════════════════════════════════════════════════

async def _run_branch(
    branch: str,
    system_prompt: str,
    query: str,
    iter_dir: Path,
    task_id: str,
    model: str,
    project_root: Path,
    semaphore: asyncio.Semaphore,
    cost_tracker: CostTracker,
) -> dict:
    """Generic agent invocation; the branch arg only affects naming + log."""
    async with semaphore:
        read_file, _ = _build_file_tools(project_root)
        agent = Agent(
            name=f"GroupDiagnoser-{branch}-{task_id}",
            instructions=system_prompt,
            model=_resolve_model(model),
            model_settings=get_model_settings(model),
            tools=[read_file],
        )

        diag_dir = iter_dir / f"group_diagnose_{task_id}"
        diag_dir.mkdir(parents=True, exist_ok=True)
        logger = TrajectoryLogger(diag_dir / "diagnosis.jsonl")

        print(f"  [group_diag/{branch}] task={task_id}")
        t0 = time.time()
        output = ""
        last_err: Exception | None = None
        for attempt in range(3):  # NEW: retry on transient connection errors
            try:
                result = Runner.run_streamed(agent, query, max_turns=15)
                await stream_with_logging(result, logger)
                output = result.final_output or ""
                delta = cost_tracker.update(result)
                cost_tracker.print_step(f"GROUP_DIAG/{branch} {task_id}", delta)
                last_err = None
                break
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                # Retry only on transient connection / rate / timeout errors
                if attempt < 2 and any(kw in err_str for kw in (
                    "connection", "timeout", "rate", "503", "504", "502",
                    "temporarily", "try again", "overloaded"
                )):
                    backoff = 5 * (2 ** attempt)
                    print(
                        f"  [group_diag/{branch}] {task_id} attempt {attempt+1} "
                        f"failed ({type(e).__name__}: {str(e)[:60]}); "
                        f"retrying in {backoff}s"
                    )
                    await asyncio.sleep(backoff)
                    continue
                # Non-transient or last attempt: bail out
                print(f"  [group_diag/{branch}] {task_id} error: {e}")
                output = f"[GROUP DIAGNOSIS ERROR] {e}"
                break
        if last_err and not output:
            output = f"[GROUP DIAGNOSIS ERROR after retries] {last_err}"
        logger.flush()

        card = _extract_card_yaml(output)
        if card is None:
            ok, violations = False, [
                "no parseable <card>...</card> block in agent output"
            ]
            card = {"group_type": branch, "task_id": task_id,
                    "diagnosis_label": "PARSE_ERROR",
                    "diagnosis_prose": output[:1000],
                    "candidate_claims": []}
        else:
            ok, violations = _validate_card(card, branch)

        # Persist raw + parsed
        _write_workspace(diag_dir / "card_raw.txt", output)
        _write_workspace(diag_dir / "card.yaml",
                         yaml.safe_dump(card, allow_unicode=True, sort_keys=False))
        if violations:
            _write_workspace(diag_dir / "violations.txt",
                             "\n".join(violations))

        return {
            "task_id": task_id,
            "branch": branch,
            "card": card,
            "ok": ok,
            "violations": violations,
            "elapsed": round(time.time() - t0, 2),
            "raw_output": output,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Public dispatcher
# ═══════════════════════════════════════════════════════════════════════════

async def run_group_diagnose(
    group_assessments: list[dict],
    group_type: str,
    task_str: str,
    iter_id: str,
    iter_dir: Path,
    skills_dir: Path,
    skill_name: str,
    model: str,
    project_root: Path,
    semaphore: asyncio.Semaphore,
    cost_tracker: CostTracker,
) -> dict:
    """Diagnose ONE group. Dispatches by ``group_type`` to the right branch.

    Returns a dict with:
      - task_id, branch, card (parsed dict), ok (bool), violations (list[str]),
        elapsed, raw_output.

    The card is the canonical Phase 2 output. ``ok`` indicates schema
    compliance; ``violations`` lists any hard-constraint breaches.
    Caller should NOT silently drop violation-flagged cards — the
    Phase 3 momentum agent reads violations as evidence-quality signal.
    """
    if not group_assessments:
        raise ValueError("empty group_assessments")
    task_id = group_assessments[0]["id"]
    skill_dir = skills_dir / skill_name

    if group_type == "mixed":
        query = _build_mixed_query(group_assessments, task_str, iter_id)
        prompt = MIXED_DIAGNOSER_PROMPT
    elif group_type == "all_fail":
        query = _build_all_fail_query(group_assessments, task_str, iter_id)
        prompt = ALL_FAIL_DIAGNOSER_PROMPT
    elif group_type == "all_success":
        query = _build_all_success_query(
            group_assessments, task_str, iter_id, skill_dir,
        )
        prompt = ALL_SUCCESS_DIAGNOSER_PROMPT
    else:
        raise ValueError(f"unknown group_type {group_type!r}")

    return await _run_branch(
        branch=group_type, system_prompt=prompt, query=query,
        iter_dir=iter_dir, task_id=str(task_id), model=model,
        project_root=project_root, semaphore=semaphore,
        cost_tracker=cost_tracker,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Batch-level assembly (one file Phase 3 momentum reads)
# ═══════════════════════════════════════════════════════════════════════════

def assemble_group_cards(
    diagnoses: list[dict], output_path: Path,
) -> Path:
    """Assemble per-group cards into a single batch_diagnostic_cards.md.

    Output is a markdown file with one ## block per group, each
    containing the parsed YAML card pretty-printed back as YAML.
    Cards with violations get a banner so downstream readers can flag
    them. This file is the Phase 3 momentum agent's primary input
    (analogous to SkillGrad's batch_diagnoses.md).
    """
    lines = ["# Batch Diagnostic Cards (Phase 2)\n"]
    for d in diagnoses:
        task_id = d["task_id"]
        branch = d["branch"]
        ok = d.get("ok", False)
        violations = d.get("violations", []) or []
        card = d.get("card", {})

        header = (
            f"\n## Task {task_id} — branch: {branch}"
            + ("" if ok else "  ⚠ VIOLATIONS")
        )
        lines.append(header + "\n")
        if violations:
            lines.append("**Schema violations:**")
            for v in violations:
                lines.append(f"- {v}")
            lines.append("")
        lines.append("```yaml")
        lines.append(yaml.safe_dump(card, allow_unicode=True, sort_keys=False).strip())
        lines.append("```")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [assemble_group_cards] Wrote {len(diagnoses)} cards "
          f"to {output_path}")
    return output_path

