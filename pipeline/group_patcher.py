"""Group patcher stage (Phase 4) — quantitative claim routing.

The patcher reads the iteration's group cards + momentum overlay +
pattern record + pending pool, applies a deterministic pre-filter that
hard-rejects `current_strength: low` patterns from the core/auxiliary
paths, then dispatches to a single LLM agent that runs the §3a routing
table from the prompt and applies §3b actions.

Pre-filter rationale: even though §3a in the prompt encodes the same
hard rule, doing it deterministically in code (a) saves tokens (the
LLM doesn't have to reason through the rule for every pending pattern)
and (b) provides a logged enforcement we can cite in ablations.

SkillGrad's original `pipeline/patcher.py` is unchanged — kept as the
N×1 single-trajectory baseline.
"""

from __future__ import annotations

import re
import time
import asyncio
from pathlib import Path
from typing import Optional

from agents import Agent, Runner

from pipeline.execution import _write_workspace
from pipeline.helpers import _build_file_tools, _resolve_model
from prompts.group_patcher import GROUP_PATCHER_PROMPT
from runners.cost_tracker import CostTracker
from runners.model_settings import get_model_settings
from runners.trajectory_logger import TrajectoryLogger, stream_with_logging


# ─── deterministic pre-filter ─────────────────────────────────────────

_PATTERN_HEADER_RE = re.compile(r"^###\s+([\w\-]+)\s*\|", re.M)
_FIELD_RE = re.compile(r"^-\s+(\w+):\s*(.*)$", re.M)


def _parse_pattern_blocks(record_text: str) -> list[dict]:
    """Best-effort extraction of pattern entries from momentum_memory.md.

    Returns a list of dicts with keys: pattern_id, current_strength,
    contradiction_count, mixed_support, source_groups (raw text).

    Markdown-embedded YAML-ish format from Phase 3's prompt; this parser
    is intentionally lenient — it's used only by the pre-filter to
    decide which patterns are 'force-pending'. The full parsing for
    correctness lives in the LLM's interpretation.
    """
    if not record_text or not record_text.strip():
        return []
    headers = list(_PATTERN_HEADER_RE.finditer(record_text))
    blocks = []
    for i, m in enumerate(headers):
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(record_text)
        body = record_text[start:end]
        pattern_id = m.group(1)
        info: dict = {"pattern_id": pattern_id}
        for fm in _FIELD_RE.finditer(body):
            k, v = fm.group(1), fm.group(2).strip()
            if k in {"current_strength", "peak_strength"}:
                info[k] = v
            elif k == "last_mixed_iter":
                info[k] = v
        # Crude evidence_profile extraction (indented "key: int" lines)
        for ek in ("mixed_support", "all_fail_support", "all_success_support",
                   "contradiction_count"):
            mm = re.search(rf"^\s+{ek}:\s*(\d+)", body, re.M)
            if mm:
                info[ek] = int(mm.group(1))
        # source_groups: capture the bracketed list as raw text
        sm = re.search(r"^\s+source_groups:\s*\[(.*?)\]", body, re.M | re.S)
        if sm:
            info["source_groups_raw"] = sm.group(1).strip()
        # NEW: negative_function flag (line "- negative_function: yes|no")
        nfm = re.search(r"^\s*-?\s*negative_function:\s*(yes|no)\b", body, re.M | re.I)
        if nfm:
            info["negative_function"] = nfm.group(1).lower() == "yes"
        else:
            info["negative_function"] = False
        # NEW Fix S: procedural_template flag
        ptm = re.search(r"^\s*-?\s*procedural_template:\s*(yes|no)\b", body, re.M | re.I)
        if ptm:
            info["procedural_template"] = ptm.group(1).lower() == "yes"
        else:
            info["procedural_template"] = False
        blocks.append(info)
    return blocks


def deterministic_prefilter(record_text: str, min_core_diversity: int = 2) -> dict:
    """Run the routing pre-filter on a momentum_memory.md text blob.

    Args:
        min_core_diversity: source_task_diversity threshold below which a
            pattern is FLAGGED (not blocked) as low-diversity. The LLM
            may still route to core if it provides explicit generalization
            rationale. (Hard-blocking diversity in v2 was too restrictive;
            the SkillGrad diagnostic showed many high-leverage L2 promotions
            come from single-task evidence.)

    Returns:
        dict with keys:
          force_pending: list of pattern_ids with current_strength=low
          low_diversity: list of pattern_ids with diversity < threshold
                         (advisory; LLM judgment governs)
          discard_candidates: list of pattern_ids with contradiction_count >= 2
          inspectable: list of pattern_ids the LLM should route normally
          all_patterns: list[pattern_id] in input order
    """
    blocks = _parse_pattern_blocks(record_text)
    force_pending: list[str] = []
    low_diversity: list[str] = []
    discard_candidates: list[str] = []
    inspectable: list[str] = []
    cross_task_convergent: list[str] = []  # NEW: function_negative candidates
    procedural_template: list[str] = []     # NEW Fix S: positive procedural primitives
    for b in blocks:
        pid = b["pattern_id"]
        cs = b.get("current_strength")
        cc = b.get("contradiction_count", 0)

        # Compute source_task_diversity from raw source_groups text
        sg_raw = b.get("source_groups_raw", "")
        task_ids = set()
        if sg_raw:
            for entry in sg_raw.split(","):
                entry = entry.strip()
                if ":" in entry:
                    task_ids.add(entry.split(":", 1)[1].strip())
        diversity = len(task_ids)

        # NEW: detect cross-task convergent candidates for function_negative routing.
        # A pattern qualifies if EITHER:
        #   (a) ≥ 2 distinct task_ids in source_groups + all_fail-only support + 0 contradiction
        #       (high-confidence cross-task corroboration), OR
        #   (b) negative_function flag set (originated from kind=function_negative card)
        #       + 0 contradiction
        #       (single-task acceptable because diagnoser already validated CONVERGENT
        #        + clean negative_only_text via deterministic literal_check)
        ms = b.get("mixed_support", 0)
        afs = b.get("all_fail_support", 0)
        ass_ = b.get("all_success_support", 0)
        nf = b.get("negative_function", False)
        is_cross_task_convergent_strong = (
            ms == 0
            and ass_ == 0
            and afs >= 2
            and diversity >= 2
            and cc == 0
        )
        is_cross_task_convergent_provisional = (
            nf
            and afs >= 1
            and ms == 0
            and ass_ == 0
            and cc == 0
        )
        is_cross_task_convergent = (
            is_cross_task_convergent_strong or is_cross_task_convergent_provisional
        )
        if is_cross_task_convergent:
            cross_task_convergent.append(pid)

        # NEW Fix S 2026-06-22: detect procedural_template patterns.
        # These come from all_success cards with kind=procedural_template.
        # Route directly to auxiliary_procedural_template (writes L3
        # chapter with code synthesized from prose). Single all_success
        # observation is enough — the technique demonstrably worked.
        is_procedural_template = bool(b.get("procedural_template", False))
        if is_procedural_template:
            procedural_template.append(pid)

        if cc >= 2:
            discard_candidates.append(pid)
        elif is_procedural_template:
            # procedural_template bypasses the strength gate — single
            # all_success is sufficient. Route handled separately.
            inspectable.append(pid)
        elif cs == "low" and not is_cross_task_convergent:
            # Force-pending applies to ordinary low-strength patterns,
            # but not to cross-task convergent patterns (those are
            # routed to core_function_negative independently).
            force_pending.append(pid)
        else:
            inspectable.append(pid)
            if diversity < min_core_diversity and not is_cross_task_convergent:
                low_diversity.append(pid)
    return {
        "force_pending": force_pending,
        "low_diversity": low_diversity,
        "discard_candidates": discard_candidates,
        "inspectable": inspectable,
        "cross_task_convergent": cross_task_convergent,  # NEW
        "procedural_template": procedural_template,      # NEW Fix S
        "min_core_diversity": min_core_diversity,
        "all_patterns": [b["pattern_id"] for b in blocks],
    }


def _format_prefilter_summary(prefilter: dict) -> str:
    """Render the pre-filter result as a human/LLM-readable preface."""
    lines = ["## Deterministic pre-filter (runner-applied)\n"]
    if prefilter["force_pending"]:
        lines.append(
            "**Force-pending** (current_strength=low; HARD CONSTRAINT, "
            "do NOT route to core/auxiliary):"
        )
        for pid in prefilter["force_pending"]:
            lines.append(f"  - {pid}")
        lines.append("")
    if prefilter["discard_candidates"]:
        lines.append(
            "**Discard candidates** (contradiction_count ≥ 2):"
        )
        for pid in prefilter["discard_candidates"]:
            lines.append(f"  - {pid}")
        lines.append("")
    if prefilter.get("low_diversity"):
        mcd = prefilter.get("min_core_diversity", 2)
        lines.append(
            f"**Low diversity ADVISORY** (source_task_diversity < {mcd}; "
            f"do NOT auto-promote to core; you MAY route to core ONLY when "
            f"you can articulate explicit generalization rationale that the "
            f"rule applies beyond its supporting tasks):"
        )
        for pid in prefilter["low_diversity"]:
            lines.append(f"  - {pid}")
        lines.append("")
    if prefilter["inspectable"]:
        lines.append(
            "**Inspectable** (route by §3a table — your decision):"
        )
        for pid in prefilter["inspectable"]:
            lines.append(f"  - {pid}")
        lines.append("")
    if prefilter.get("cross_task_convergent"):
        lines.append(
            "**Cross-task convergent (NEW route: core_function_negative)** — "
            "these patterns are eligible for the **core_function_negative** "
            "route under EITHER of these qualification conditions:\n"
            "  (a) STRONG: CONVERGENT all_fail support across ≥ 2 distinct "
            "task_ids with no contradicting success, OR\n"
            "  (b) PROVISIONAL: pattern's `negative_function: yes` flag is "
            "set (originated from a `kind=function_negative` diagnose card "
            "where the diagnoser already validated CONVERGENT + clean "
            "negative_only_text + literal_check), with ≥ 1 all_fail "
            "support and 0 contradiction.\n"
            "**HARD CONSTRAINT**: Route them to `core_function_negative` "
            "per §3a, REGARDLESS of `current_strength` value. Their "
            "current_strength may read `low` (since all_fail-only support "
            "naturally maps to low under §3a's table), but the prefilter "
            "lists them HERE precisely to override that — they get the "
            "function_negative path instead of the standard low → "
            "force_pending path. Emit them as `<!-- F: avoid -->` blocks "
            "anchored to the most relevant existing process H2 per §3b "
            "`core_function_negative` action.\n"
            "Patterns flagged here:"
        )
        for pid in prefilter["cross_task_convergent"]:
            lines.append(f"  - {pid}")
        lines.append("")
    if prefilter.get("procedural_template"):
        lines.append(
            "**Procedural template (NEW Fix S route: auxiliary_procedural_template)** — "
            "these patterns originated from `kind=procedural_template` "
            "all_success cards. They capture GENERIC procedural primitives "
            "(header_mapping, output_file_write, worksheet_presence_check, "
            "etc.) that the rollouts demonstrated work. Equivalent to v8+FIX's "
            "L3 chapter inventory.\n"
            "**HARD CONSTRAINT**: Route them to `auxiliary_procedural_template` "
            "per §3a/§3b, REGARDLESS of `current_strength` value. Single "
            "all_success observation is sufficient — the technique "
            "demonstrably worked. Emit as L3 chapter at "
            "`references/<technique-name>.md` (with Python code synthesized "
            "from procedure_prose) + L2 imperative pointer in SKILL.md "
            "(\"Read references/X.md when Y. Skip when Z.\" form).\n"
            "Patterns flagged here:"
        )
        for pid in prefilter["procedural_template"]:
            lines.append(f"  - {pid}")
        lines.append("")
    if not (prefilter["force_pending"] or prefilter["discard_candidates"]
            or prefilter.get("low_diversity") or prefilter["inspectable"]
            or prefilter.get("cross_task_convergent")):
        lines.append("(no patterns parsed; check momentum_memory.md)")
    return "\n".join(lines)


# ─── main runner ─────────────────────────────────────────────────────


def _build_adherence_block(adherence_summary_path: Path | None) -> str:
    """SAPR-minimal: append adherence signal block to patcher query.

    Generic format (no rule-hardcoding per [[g2b-sapr-a0a5-prereg]]).
    Empty string if no path provided (A0 baseline).
    """
    if adherence_summary_path is None or not adherence_summary_path.exists():
        return ""
    try:
        body = adherence_summary_path.read_text(encoding="utf-8")
    except Exception:
        return ""
    return (
        "\n## Adherence signal (SAPR-minimal)\n\n"
        + body
        + "\n**Patcher instruction (generic):** when proposing patches, "
          "prioritize the LOW_ADH_ON_FAIL and HIGH_ADH_ON_FAIL flagged "
          "rules above. For LOW_ADH_ON_FAIL, edit prominence/wording/"
          "position only — do NOT rewrite content. For HIGH_ADH_ON_FAIL, "
          "edit content/decision logic — do NOT touch prominence. Apply "
          "this signal across all flagged rules; do not single out any "
          "specific rule a priori.\n"
    )


async def run_group_patch(
    cards_path: Path,
    overlay_path: Path,
    record_path: Path,
    pending_pool_path: Path,
    skills_dir: Path,
    skill_name: str,
    model: str,
    project_root: Path,
    cost_tracker: CostTracker,
    iter_dir: Path,
    iter_num: int,
    fix_coreset_ids: list[str] | None = None,
    adherence_summary_path: Path | None = None,
) -> dict:
    """Run the group patcher for one iteration.

    Reads the pattern record, applies the deterministic pre-filter, then
    invokes the LLM patcher with the pre-filter results surfaced in the
    query. The LLM still produces the actual edits to SKILL.md /
    references/*.md / pending_pool.md.

    ``fix_coreset_ids`` is the list of base-fail tasks the agent has
    previously demonstrated success on. Surfaced to the patcher as a
    "preserve these capabilities" hint — the patcher should avoid
    rules that would conflict with how those tasks were solved.

    Returns a dict with the parsed routing decisions (best-effort) and
    cost / timing info.
    """
    read_file, write_file = _build_file_tools(project_root)

    record_text = ""
    if record_path.exists():
        record_text = record_path.read_text(encoding="utf-8")
    prefilter = deterministic_prefilter(record_text)
    prefilter_md = _format_prefilter_summary(prefilter)

    # Persist the pre-filter result so we can audit + ablate later.
    _write_workspace(iter_dir / "prefilter_summary.md", prefilter_md)

    # Ensure pending_pool.md exists (empty header at iter 1).
    if not pending_pool_path.exists():
        pending_pool_path.write_text(
            "# Pending pool\n\n"
            "Low-strength candidate patterns awaiting mixed-group "
            "corroboration. Phase 4 appends here when "
            "`current_strength: low` or routing fails the §3a criteria.\n",
            encoding="utf-8",
        )

    routing_decisions_path = iter_dir / "routing_decisions.md"

    skill_dir = skills_dir / skill_name
    skill_files = [str(skill_dir / "SKILL.md")]
    refs_dir = skill_dir / "references"
    if refs_dir.exists():
        for f in sorted(refs_dir.iterdir()):
            if f.is_file():
                skill_files.append(str(f))

    fix_coreset_block = ""
    if fix_coreset_ids:
        fix_coreset_block = (
            f"\n## Preserve-capabilities hint (fix coreset)\n\n"
            f"The current skill (before this iter's patch) has shown the "
            f"agent can pass these {len(fix_coreset_ids)} base-failure tasks: "
            f"{', '.join(sorted(fix_coreset_ids)[:32])}"
            f"{' (+more)' if len(fix_coreset_ids) > 32 else ''}\n\n"
            f"This is GUIDANCE, not a constraint: when proposing rules, "
            f"prefer phrasings that DON'T contradict whatever made those "
            f"tasks succeed — but DO still promote good rules to L2. "
            f"Being too conservative (everything → auxiliary/pending) "
            f"starves the executor of L2 content and makes the skill "
            f"effectively useless. The bilateral regression gate after "
            f"this patch will catch true regressions deterministically; "
            f"your job is to maximize L2 coverage while staying broadly "
            f"compatible with these existing capabilities.\n"
        )

    query = (
        f"This is iteration {iter_num}.\n\n"
        f"## Inputs\n"
        f"- Group cards: {cards_path}\n"
        f"- Overlay:     {overlay_path}\n"
        f"- Pattern record: {record_path}\n"
        f"- Pending pool:   {pending_pool_path}\n"
        f"- Current skill files:\n"
        + "\n".join(f"    - {p}" for p in skill_files)
        + "\n"
        f"- Reference dir for new L3 files: {refs_dir}\n"
        f"  (Create files there for new L3 chapters; may not exist yet.)\n\n"
        f"## Outputs you must write\n"
        f"- SKILL.md edits (only for `route: core` patterns)\n"
        f"- references/*.md edits (for L3 chapters from `route: core` and "
        f"  `route: auxiliary`)\n"
        f"- {pending_pool_path}  (append for `route: pending`)\n"
        f"- {routing_decisions_path}  (one row per pattern, MANDATORY)\n\n"
        f"## Pre-filter context\n\n"
        f"{prefilter_md}\n\n"
        f"Force-pending and discard candidates are pre-decided by the "
        f"runner. You still write their `pending_pool.md` entries (for "
        f"force-pending) and the `routing_decisions.md` rows (for both). "
        f"For inspectable patterns, run the §3a routing table.\n"
        f"{fix_coreset_block}"
        f"{_build_adherence_block(adherence_summary_path)}"
    )

    logger = TrajectoryLogger(iter_dir / "group_patcher.jsonl")
    print(
        f"  [group_patch] iter {iter_num}: "
        f"prefilter force_pending={len(prefilter['force_pending'])} "
        f"discard={len(prefilter['discard_candidates'])} "
        f"inspectable={len(prefilter['inspectable'])}"
    )
    t0 = time.time()
    output = ""
    last_err: Exception | None = None
    for attempt in range(3):  # NEW: retry on transient connection errors
        try:
            agent = Agent(
                name="GroupPatcher",
                instructions=GROUP_PATCHER_PROMPT,
                model=_resolve_model(model),
                model_settings=get_model_settings(model),
                tools=[read_file, write_file],
            )
            result = Runner.run_streamed(agent, query, max_turns=25)
            await stream_with_logging(result, logger)
            output = result.final_output or ""
            delta = cost_tracker.update(result)
            cost_tracker.print_step("GROUP_PATCH", delta)
            last_err = None
            break
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            if attempt < 2 and any(kw in err_str for kw in (
                "connection", "timeout", "rate", "503", "504", "502",
                "temporarily", "try again", "overloaded"
            )):
                backoff = 5 * (2 ** attempt)
                print(
                    f"  [group_patch] attempt {attempt+1} failed "
                    f"({type(e).__name__}: {str(e)[:60]}); "
                    f"retrying in {backoff}s"
                )
                await asyncio.sleep(backoff)
                continue
            print(f"  [group_patch] error: {e}")
            output = f"[GROUP PATCH ERROR] {e}"
            break
    if last_err and not output:
        output = f"[GROUP PATCH ERROR after retries] {last_err}"
    logger.flush()
    elapsed = round(time.time() - t0, 2)
    print(f"  [group_patch] Done in {elapsed}s")

    # Persist the agent's final message + best-effort routing summary.
    _write_workspace(iter_dir / "patcher_final_message.md", output)

    # Read routing decisions back if the agent emitted them.
    routing_summary: list[dict] = []
    if routing_decisions_path.exists():
        try:
            text = routing_decisions_path.read_text(encoding="utf-8")
            for line in text.splitlines():
                # crude markdown-table parse: | id | route | ...
                if line.startswith("|") and "|" in line[1:]:
                    cells = [c.strip() for c in line.strip("|").split("|")]
                    if len(cells) >= 2 and cells[1] in (
                        "core", "auxiliary", "pending", "discard",
                    ):
                        routing_summary.append({
                            "pattern_id": cells[0], "route": cells[1],
                            "raw_row": line,
                        })
        except Exception:
            pass

    return {
        "elapsed": elapsed,
        "prefilter": prefilter,
        "routing_summary": routing_summary,
        "patcher_output": output,
    }
