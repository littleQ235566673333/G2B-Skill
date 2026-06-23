"""Step 2: Patchability pre-check for PTB direction.

Sample 20 diagnoses (10 from GPT-4.1 WTQ + 10 from GPT-5.4 SS) and have GPT-5.4
judge whether each can be extracted into a patch card (trigger + action_rule +
verification, ≤80 tokens total).

Pass criteria: yes ≥ 50% AND yes+partial ≥ 70%.
"""
from __future__ import annotations
import asyncio
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"

from agents import Agent, Runner

from pipeline.helpers import _resolve_model
from runners.cost_tracker import CostTracker
from runners.model_settings import get_model_settings


JUDGE_PROMPT = """\
You judge whether an agent diagnosis can be turned into a compact "patch card" \
suitable for runtime injection into a task executor's prompt.

A patch card has THREE components, all packed into ≤80 tokens total:

1. **trigger** (≤25 tokens): a single phrase describing what task/input feature \
selects this patch. Must be a recognizable surface pattern (keyword, formula \
shape, output type, etc.), not a vague meta-description.

2. **action_rule** (≤40 tokens): 1-3 imperative sentences telling the executor \
exactly what to do. Must be concrete and verifiable, not aspirational.

3. **verification** (≤15 tokens): one short check the executor can perform on \
its output to confirm correctness.

Given the diagnosis, judge:

- **yes**: All three components can be cleanly extracted, total stays under 80 tokens.
- **partial**: 2 of 3 components extractable, OR all 3 but total exceeds 80 tokens.
- **no**: Cannot extract trigger or action_rule, OR diagnosis is abstract \
summary with no actionable content.

Output a JSON object with these fields:
  verdict: "yes" | "partial" | "no"
  trigger: extracted trigger phrase (or "" if not extractable)
  action_rule: extracted action rule (or "" if not extractable)
  verification: extracted verification (or "" if not extractable)
  total_tokens: rough token count estimate of (trigger + action_rule + verification)
  rationale: 1 sentence explaining the verdict

Output ONLY the JSON object, no markdown fences, no commentary.
"""


def collect_diagnoses(run_root: Path, n_target: int, rng: random.Random) -> list[dict]:
    """Walk all iter_N/diagnose_X/diagnosis.txt under run_root/train/, sample n_target."""
    base = run_root / "train"
    candidates = []
    for iter_dir in base.glob("iter_*"):
        for d in iter_dir.glob("diagnose_*"):
            f = d / "diagnosis.txt"
            if f.exists():
                text = f.read_text(encoding="utf-8").strip()
                if len(text) > 100:  # skip tiny/empty
                    candidates.append({
                        "path": str(f.relative_to(Path("results/runs").resolve().parent.parent)) if str(f).startswith(str(Path("results/runs").resolve())) else str(f),
                        "text": text,
                        "task": d.name.replace("diagnose_", ""),
                    })
    rng.shuffle(candidates)
    return candidates[:n_target]


async def judge_one(agent: Agent, diagnosis_text: str, cost: CostTracker) -> dict:
    query = f"Diagnosis to evaluate:\n\n{diagnosis_text}"
    result = Runner.run_streamed(agent, query, max_turns=2)
    async for _ in result.stream_events():
        pass
    cost.update(result)
    out = (result.final_output or "").strip()
    # Strip code fences if present
    if out.startswith("```"):
        out = out.split("\n", 1)[1] if "\n" in out else out
        out = out.rsplit("```", 1)[0].strip()
        if out.startswith("json"):
            out = out[4:].strip()
    try:
        return json.loads(out)
    except Exception as e:
        return {"verdict": "parse_error", "raw": out, "err": str(e)}


async def main_async():
    rng = random.Random(0)

    print("=== Step 2: Patchability pre-check ===")
    print("Sampling 10 diagnoses from each of:")
    print("  - GPT-4.1 WTQ + anti-wipe fix")
    print("  - GPT-5.4 SS")
    print()

    samples_a = collect_diagnoses(
        Path("results/runs/g2b-v8_gpt-4.1_wtq-gpt41-fix").resolve(), 10, rng,
    )
    samples_b = collect_diagnoses(
        Path("results/runs/g2b-v8_gpt-5.4").resolve(), 10, rng,
    )
    print(f"GPT-4.1 WTQ samples: {len(samples_a)}")
    print(f"GPT-5.4 SS samples:  {len(samples_b)}")
    samples = [(s, "gpt-4.1-wtq") for s in samples_a] + [(s, "gpt-5.4-ss") for s in samples_b]

    # Build judge agent
    cost = CostTracker("gpt-5.4")
    agent = Agent(
        name="PatchabilityJudge",
        instructions=JUDGE_PROMPT,
        model=_resolve_model("gpt-5.4"),
        model_settings=get_model_settings("gpt-5.4", temperature=0.0),
        tools=[],
    )

    print("\nJudging (each diagnosis × 2 reps, gpt-5.4 temp=0)...")
    results = []
    for i, (sample, source) in enumerate(samples):
        j1 = await judge_one(agent, sample["text"], cost)
        j2 = await judge_one(agent, sample["text"], cost)
        v1, v2 = j1.get("verdict", "?"), j2.get("verdict", "?")
        # Conservative aggregation: if disagree, take lower rank
        rank = {"yes": 2, "partial": 1, "no": 0, "parse_error": -1}
        if v1 == v2:
            final = v1
        else:
            final = v1 if rank.get(v1, -1) < rank.get(v2, -1) else v2
        agreement = (v1 == v2)
        results.append({
            "idx": i,
            "source": source,
            "task": sample["task"],
            "path": sample["path"],
            "diagnosis_excerpt": sample["text"][:300],
            "diagnosis_full": sample["text"],
            "j1": j1,
            "j2": j2,
            "final_verdict": final,
            "agreement": agreement,
        })
        print(f"  [{i+1:>2}/20] source={source:>11} task={sample['task']:>10} | j1={v1} j2={v2} → final={final} {'✓' if agreement else '⚠'}")

    # Aggregate
    n_yes = sum(1 for r in results if r["final_verdict"] == "yes")
    n_partial = sum(1 for r in results if r["final_verdict"] == "partial")
    n_no = sum(1 for r in results if r["final_verdict"] == "no")
    n_parse_err = sum(1 for r in results if r["final_verdict"] == "parse_error")
    n_disagreement = sum(1 for r in results if not r["agreement"])
    total = len(results)

    print()
    print("=" * 60)
    print(f"AGGREGATE (n={total})")
    print("=" * 60)
    print(f"  yes:        {n_yes}/{total} = {n_yes/total*100:.0f}%")
    print(f"  partial:    {n_partial}/{total} = {n_partial/total*100:.0f}%")
    print(f"  no:         {n_no}/{total} = {n_no/total*100:.0f}%")
    print(f"  parse_err:  {n_parse_err}/{total}")
    print(f"  disagreement (j1 vs j2): {n_disagreement}/{total}")
    print()
    yes_pct = n_yes / total * 100
    yp_pct = (n_yes + n_partial) / total * 100
    pass_yes = n_yes >= 10  # ≥ 50%
    pass_yp = (n_yes + n_partial) >= 14  # ≥ 70%
    print(f"Pass criteria:")
    print(f"  yes ≥ 50%:        {n_yes}/20 ≥ 10? {'PASS' if pass_yes else 'FAIL'} ({yes_pct:.0f}%)")
    print(f"  yes+partial ≥ 70%: {n_yes+n_partial}/20 ≥ 14? {'PASS' if pass_yp else 'FAIL'} ({yp_pct:.0f}%)")
    print()
    overall = "GO" if (pass_yes and pass_yp) else "NO-GO"
    print(f"DECISION: {overall}")
    print()

    # Print 3 "yes" full diagnoses + extracted patches for human spot check
    print("=" * 60)
    print('SPOT CHECK — 3 "yes" diagnoses (full text + extracted patches)')
    print("=" * 60)
    yes_results = [r for r in results if r["final_verdict"] == "yes"][:3]
    for i, r in enumerate(yes_results, 1):
        print(f"\n--- yes-{i} ---")
        print(f"  source: {r['source']}, task: {r['task']}")
        print(f"  full diagnosis:")
        for line in r["diagnosis_full"].split("\n"):
            print(f"    {line}")
        print(f"  judge1 extracted: trigger='{r['j1'].get('trigger','')}'")
        print(f"                    action='{r['j1'].get('action_rule','')}'")
        print(f"                    verify='{r['j1'].get('verification','')}'")
        print(f"                    rationale: {r['j1'].get('rationale','')}")

    # Save full results
    out_path = Path("analysis/ptb_step2_patchability.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "summary": {
            "n_total": total, "n_yes": n_yes, "n_partial": n_partial,
            "n_no": n_no, "n_parse_err": n_parse_err,
            "n_disagreement": n_disagreement,
            "yes_pct": yes_pct, "yes_partial_pct": yp_pct,
            "decision": overall, "cost": cost.total_cost,
        },
        "results": results,
    }, indent=2), encoding="utf-8")
    print(f"\nSaved: {out_path}")
    print(f"Cost: ${cost.total_cost:.3f}")


if __name__ == "__main__":
    asyncio.run(main_async())
