#!/usr/bin/env python3
"""Round 2: per-rule adherence judge on 27 tasks across 4 fail_modes."""
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

OUT_DIR = Path("results/sanity_adherence")
EVAL_DIR = "results/runs/g2b-v8_gpt-5.4/eval_100slice_multiseed"

RULES = {
    "R1_classify_deliverable": "Before writing output, did the rollout inspect workbook structure (sheet names, populated ranges, headers, examples) and classify the task as data-edit / formula-write / formatting / code-response BEFORE coding?",
    "R2_layout_inspection": "Before mapping source-to-target, did the rollout inspect actual headers and sample rows to derive real source/target columns, rather than mapping by header text equality alone?",
    "R3_stateful_simulate": "If the task involved stateful traversal (scan with restart/skip/continue), did the rollout dry-run the traversal on a concrete sheet example before coding? If task did NOT involve stateful traversal, return N/A.",
    "R4_block_aware": "If the sheet had blank-row-separated regions, did the rollout detect blocks and operate per-block rather than over the whole used range? If task had no blank-separated regions, return N/A.",
    "R5_verify_output": "After saving output.xlsx, did the rollout reopen and verify that evaluator-visible target cells contain exact expected final values (not formula-strings or stale state)?",
}

JUDGE_PROMPT = """You are evaluating whether an agent's execution trace adhered to a specific rule when working on an Excel spreadsheet task.

RULE: {rule_text}

EXECUTION TRACE (truncated):
{trace}

Output a single JSON object:
{{
  "applicable": <true|false>,
  "adhered": <0.0-1.0>,
  "evidence": "<one sentence quote/paraphrase from trace>"
}}

Output JSON only, no other text."""


def collect_round2():
    selection = json.load(open(OUT_DIR / "task_selection_round2.json"))
    rollouts = []
    for fail_mode, tids in selection.items():
        for tid in tids:
            for seed in [0, 1, 2]:
                p = Path(f"{EVAL_DIR}/task_{tid}_s{seed}/execution_trace_r0.md")
                if not p.exists(): continue
                trace = p.read_text(errors="ignore")
                rollouts.append({
                    "task_id": tid,
                    "seed": seed,
                    "fail_mode": fail_mode,
                    "trace": trace,
                })
    return rollouts


def judge_one(rollout, rule_id, rule_text):
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
    rollouts = collect_round2()
    print(f"  rollouts: {len(rollouts)}, rules: {len(RULES)}, calls: {len(rollouts) * len(RULES)}")

    jobs = [(r, rid, rtext) for r in rollouts for rid, rtext in RULES.items()]

    results = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(judge_one, r, rid, rtext): None for r, rid, rtext in jobs}
        for i, fut in enumerate(as_completed(futs)):
            results.append(fut.result())
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(jobs)}")

    out_path = OUT_DIR / "judgements_round2.jsonl"
    with open(out_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    n_ok = sum(1 for r in results if r.get("ok"))
    print(f"  ok={n_ok}/{len(results)}")
    print(f"  saved to {out_path}")


if __name__ == "__main__":
    main()
