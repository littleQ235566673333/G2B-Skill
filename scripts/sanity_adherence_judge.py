#!/usr/bin/env python3
"""Per-(rollout, rule) adherence judging via cheap LLM."""
import json
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

OUT_DIR = Path("results/sanity_adherence")
RULES_PATH = OUT_DIR / "rules.json"
ROLLOUTS_PATH = OUT_DIR / "rollouts_inventory.json"
JUDGEMENTS_PATH = OUT_DIR / "judgements.jsonl"

RULES = {
    "R1_classify_deliverable": "Before writing output, did the rollout inspect workbook structure (sheet names, populated ranges, headers, examples) and classify the task as data-edit / formula-write / formatting / code-response BEFORE coding?",
    "R2_layout_inspection": "Before mapping source-to-target, did the rollout inspect actual headers and sample rows to derive real source/target columns, rather than mapping by header text equality alone?",
    "R3_stateful_simulate": "If the task involved stateful traversal (scan with restart/skip/continue), did the rollout dry-run the traversal on a concrete sheet example before coding? If task did NOT involve stateful traversal, return N/A.",
    "R4_block_aware": "If the sheet had blank-row-separated regions, did the rollout detect blocks and operate per-block rather than over the whole used range? If task had no blank-separated regions, return N/A.",
    "R5_verify_output": "After saving output.xlsx, did the rollout reopen and verify that evaluator-visible target cells contain exact expected final values (not formula-strings or stale state)?",
}
json.dump(RULES, open(RULES_PATH, "w"), indent=2)


JUDGE_PROMPT = """You are evaluating whether an agent's execution trace adhered to a specific rule when working on an Excel spreadsheet task.

RULE: {rule_text}

EXECUTION TRACE (truncated):
{trace}

Output a single JSON object:
{{
  "applicable": <true|false>,   // is this rule applicable to this task at all?
  "adhered": <0.0-1.0>,            // 0=clearly violated, 0.5=partial, 1.0=clearly followed; meaningful only if applicable=true
  "evidence": "<one sentence quote/paraphrase from trace>"
}}

Output JSON only, no other text."""


def judge_one(rollout: dict, rule_id: str, rule_text: str) -> dict:
    """Make 1 LLM call to judge adherence."""
    from openai import OpenAI
    client = OpenAI()
    trace_truncated = rollout["trace"][:6000]
    prompt = JUDGE_PROMPT.format(rule_text=rule_text, trace=trace_truncated)
    try:
        resp = client.chat.completions.create(
            model="gpt-5.4",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
        return {
            "task_id": rollout["task_id"],
            "seed": rollout["seed"],
            "fail_mode": rollout["fail_mode"],
            "rule_id": rule_id,
            "applicable": result.get("applicable"),
            "adhered": result.get("adhered"),
            "evidence": result.get("evidence", "")[:200],
            "ok": True,
        }
    except Exception as e:
        return {
            "task_id": rollout["task_id"],
            "seed": rollout["seed"],
            "fail_mode": rollout["fail_mode"],
            "rule_id": rule_id,
            "ok": False,
            "error": str(e)[:200],
        }


def main():
    rollouts = json.load(open(ROLLOUTS_PATH))
    # re-load full traces (inventory lost them)
    sys.path.insert(0, str(Path(__file__).parent))
    from sanity_adherence_collect import collect_rollouts
    rollouts_full = collect_rollouts()
    print(f"  rollouts={len(rollouts_full)}, rules={len(RULES)}, total_calls={len(rollouts_full)*len(RULES)}")

    jobs = []
    for r in rollouts_full:
        for rid, rtext in RULES.items():
            jobs.append((r, rid, rtext))

    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(judge_one, r, rid, rtext): (r, rid) for r, rid, rtext in jobs}
        for i, fut in enumerate(as_completed(futs)):
            res = fut.result()
            results.append(res)
            if (i + 1) % 10 == 0:
                print(f"  done {i + 1}/{len(jobs)}")

    with open(JUDGEMENTS_PATH, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    n_ok = sum(1 for r in results if r.get("ok"))
    print(f"  ok={n_ok}/{len(results)}")
    print(f"  judgements at {JUDGEMENTS_PATH}")


if __name__ == "__main__":
    main()
