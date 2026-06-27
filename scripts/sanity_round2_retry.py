#!/usr/bin/env python3
"""Retry failed judge calls with backoff."""
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
sys.path.insert(0, str(Path(__file__).parent))
from sanity_round2_judge import RULES, judge_one, collect_round2

OUT_DIR = Path("results/sanity_adherence")
JUDGEMENTS_PATH = OUT_DIR / "judgements_round2.jsonl"


def load_existing():
    """Returns dict {(task_id, seed, rule_id): result}."""
    existing = {}
    for line in open(JUDGEMENTS_PATH):
        r = json.loads(line)
        if r.get("ok"):
            key = (r["task_id"], r["seed"], r["rule_id"])
            existing[key] = r
    return existing


def judge_with_retry(rollout, rule_id, rule_text, max_retries=4):
    for attempt in range(max_retries):
        result = judge_one(rollout, rule_id, rule_text)
        if result.get("ok"):
            return result
        # backoff
        time.sleep((1.5 ** attempt) + (attempt * 0.5))
    return result  # last failure


def main():
    rollouts = collect_round2()
    existing = load_existing()
    print(f"  total rollouts: {len(rollouts)}, existing OK: {len(existing)}")

    todo = []
    for r in rollouts:
        for rid, rtext in RULES.items():
            key = (r["task_id"], r["seed"], rid)
            if key not in existing:
                todo.append((r, rid, rtext))
    print(f"  to redo: {len(todo)}")

    new_results = []
    with ThreadPoolExecutor(max_workers=4) as ex:  # fewer workers to reduce rate
        futs = {ex.submit(judge_with_retry, r, rid, rtext): None for r, rid, rtext in todo}
        for i, fut in enumerate(as_completed(futs)):
            new_results.append(fut.result())
            if (i + 1) % 20 == 0:
                ok_so_far = sum(1 for r in new_results if r.get("ok"))
                print(f"  retried {i+1}/{len(todo)} (ok={ok_so_far})")

    # Append new (only OK ones, plus replace old failures)
    all_ok = list(existing.values())
    new_ok = [r for r in new_results if r.get("ok")]
    all_ok.extend(new_ok)
    new_fail = [r for r in new_results if not r.get("ok")]

    with open(JUDGEMENTS_PATH, "w") as f:
        for r in all_ok:
            f.write(json.dumps(r) + "\n")
        for r in new_fail:
            f.write(json.dumps(r) + "\n")

    print(f"\n  final: {len(all_ok)} ok, {len(new_fail)} still failing")


if __name__ == "__main__":
    main()
