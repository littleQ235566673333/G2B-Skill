"""Step 2.5: Trigger retrievability classification.

For each of the 20 'yes' patches from Step 2, classify the trigger as:
  - keyword-based: trigger references concrete surface tokens that appear (or
    appear with simple lemmatization) in the task prompt directly
  - behavioral: trigger describes task structure/pattern; identifiable but not
    from single keyword; could be matched via embedding or expanded keywords
  - abstract-semantic: trigger requires LLM-level inference over task content
    (e.g., 'features absent as columns', 'multi-step mapping required')

Decision matrix:
  keyword ≥ 60%: simple retrieval (BM25 / token overlap) feasible. Step 3 OK.
  keyword + behavioral ≥ 80%, abstract ≤ 20%: embedding retrieval feasible.
    Step 3 should test embedding retrieval, not just keyword.
  abstract ≥ 30%: simple retrieval insufficient. Need LLM-as-retriever, which
    doubles per-task cost. Step 3 design needs to factor this.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"

from agents import Agent, Runner

from pipeline.helpers import _resolve_model
from runners.cost_tracker import CostTracker
from runners.model_settings import get_model_settings


CLASSIFY_PROMPT = """\
You classify a patch's "trigger" string by what kind of retrieval mechanism \
could match it to a task at runtime.

Categories:

1. **keyword**: Trigger references concrete surface tokens that would appear \
in a task prompt directly or via simple lemmatization. Examples:
   - "questions asking 'who' with best/max score"  → matches tasks containing "who" + "best/max score"
   - "SUMIFS with multi-criteria list"             → matches tasks naming SUMIFS
   - "INDEX/MATCH with two criteria across columns" → matches "INDEX/MATCH" + criteria words
   Simple BM25 / token overlap retrieval is feasible.

2. **behavioral**: Trigger describes a task structure, pattern, or operation \
class. Identifiable but not from a single keyword in the task prompt — \
requires recognizing the pattern. Examples:
   - "streak/aggregation questions with variant headers"
   - "multi-step transformation with row-wise dependency"
   - "consecutive matching across rows"
   Embedding-similarity retrieval feasible if task descriptions encode the pattern.

3. **abstract-semantic**: Trigger requires LLM-level semantic inference about \
the task — going beyond surface tokens or behavior pattern to inferring \
high-level meaning, intent, or table-structure properties. Examples:
   - "features absent as explicit columns"
   - "destination range has prefilled examples but rule unspecified"
   - "task requires both column-mapping and row-axis decision"
   Simple retrieval likely fails. Needs LLM-as-retriever or rich annotation.

Output a JSON object:
  category: "keyword" | "behavioral" | "abstract-semantic"
  rationale: 1 sentence explaining why
  retrievable_via: list of feasible mechanisms ["bm25", "embedding", "llm"]

Output ONLY the JSON, no markdown fences.
"""


async def classify_one(agent: Agent, trigger: str, cost: CostTracker) -> dict:
    query = f"Trigger to classify: {trigger}"
    result = Runner.run_streamed(agent, query, max_turns=2)
    async for _ in result.stream_events():
        pass
    cost.update(result)
    out = (result.final_output or "").strip()
    if out.startswith("```"):
        out = out.split("\n", 1)[1] if "\n" in out else out
        out = out.rsplit("```", 1)[0].strip()
        if out.startswith("json"):
            out = out[4:].strip()
    try:
        return json.loads(out)
    except Exception as e:
        return {"category": "parse_error", "raw": out, "err": str(e)}


async def main_async():
    # Load Step 2 results
    step2 = json.load(open("analysis/ptb_step2_patchability.json"))
    yes_results = [r for r in step2["results"] if r["final_verdict"] == "yes"]
    print(f"Loaded {len(yes_results)} yes-verdict patches from Step 2")

    cost = CostTracker("gpt-5.4")
    agent = Agent(
        name="TriggerClassifier",
        instructions=CLASSIFY_PROMPT,
        model=_resolve_model("gpt-5.4"),
        model_settings=get_model_settings("gpt-5.4", temperature=0.0),
        tools=[],
    )

    print("\nClassifying triggers...")
    classifications = []
    for i, r in enumerate(yes_results):
        trigger = r["j1"].get("trigger", "")
        cls = await classify_one(agent, trigger, cost)
        cat = cls.get("category", "?")
        classifications.append({
            "idx": i,
            "source": r["source"],
            "task": r["task"],
            "trigger": trigger,
            "category": cat,
            "rationale": cls.get("rationale", ""),
            "retrievable_via": cls.get("retrievable_via", []),
        })
        print(f"  [{i+1:>2}/{len(yes_results)}] {r['source']:>12} {r['task']:>10} | {cat:>17} | {trigger[:80]}")

    # Aggregate
    n_kw = sum(1 for c in classifications if c["category"] == "keyword")
    n_beh = sum(1 for c in classifications if c["category"] == "behavioral")
    n_abs = sum(1 for c in classifications if c["category"] == "abstract-semantic")
    n_err = sum(1 for c in classifications if c["category"] == "parse_error")
    total = len(classifications)

    print()
    print("=" * 60)
    print(f"AGGREGATE (n={total})")
    print("=" * 60)
    print(f"  keyword:           {n_kw}/{total} = {n_kw/total*100:.0f}%")
    print(f"  behavioral:        {n_beh}/{total} = {n_beh/total*100:.0f}%")
    print(f"  abstract-semantic: {n_abs}/{total} = {n_abs/total*100:.0f}%")
    print(f"  parse_error:       {n_err}/{total}")

    # Per source
    print()
    for src in ["gpt-4.1-wtq", "gpt-5.4-ss"]:
        src_cls = [c for c in classifications if c["source"] == src]
        if not src_cls: continue
        kw = sum(1 for c in src_cls if c["category"] == "keyword")
        beh = sum(1 for c in src_cls if c["category"] == "behavioral")
        absm = sum(1 for c in src_cls if c["category"] == "abstract-semantic")
        n = len(src_cls)
        print(f"  {src}: keyword={kw}/{n}, behavioral={beh}/{n}, abstract={absm}/{n}")

    # Decision per Opus matrix
    print()
    print("=" * 60)
    kw_pct = n_kw / total * 100
    kb_pct = (n_kw + n_beh) / total * 100
    abs_pct = n_abs / total * 100

    if kw_pct >= 60:
        decision = "GO STEP 3 (simple BM25/token retrieval feasible)"
    elif kb_pct >= 80 and abs_pct <= 20:
        decision = "GO STEP 3 with EMBEDDING retrieval (Step 3 design must test embedding, not keyword)"
    elif abs_pct >= 30:
        decision = "STEP 3 NEEDS REDESIGN (abstract triggers ≥ 30% → need LLM-as-retriever, double cost)"
    else:
        decision = "MIXED (manual review needed)"
    print(f"DECISION: {decision}")
    print()

    # Show GPT-5.4 SS yes spot check (balance vs prior all-WTQ display)
    print("=" * 60)
    print("SPOT CHECK — GPT-5.4 SS yes diagnoses (3 samples)")
    print("=" * 60)
    ss_yes = [r for r in step2["results"] if r["final_verdict"] == "yes" and r["source"] == "gpt-5.4-ss"][:3]
    for i, r in enumerate(ss_yes, 1):
        print(f"\n--- SS yes-{i} (task {r['task']}) ---")
        print(f"  trigger: {r['j1'].get('trigger','')}")
        print(f"  action:  {r['j1'].get('action_rule','')}")
        print(f"  verify:  {r['j1'].get('verification','')}")
        # Show first 200 chars of full diagnosis for context
        print(f"  diagnosis (first 200 chars): {r['diagnosis_full'][:200]}...")

    out_path = Path("analysis/ptb_step2_5_retrievability.json")
    out_path.write_text(json.dumps({
        "summary": {"n_total": total, "n_keyword": n_kw, "n_behavioral": n_beh,
                    "n_abstract": n_abs, "kw_pct": kw_pct, "kb_pct": kb_pct,
                    "abs_pct": abs_pct, "decision": decision, "cost": cost.total_cost},
        "classifications": classifications,
    }, indent=2))
    print(f"\nSaved: {out_path}")
    print(f"Cost: ${cost.total_cost:.3f}")


if __name__ == "__main__":
    asyncio.run(main_async())
