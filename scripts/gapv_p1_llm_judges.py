"""GAPV P1 LLM judges (2, 3a, 3b) per pre-reg v2.1."""
import json, os, pickle, asyncio
from pathlib import Path

with open('.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            os.environ[k] = v.strip("'\"")

from openai import OpenAI
client = OpenAI()

# Load intermediate
with open('/tmp/gapv_p1_intermediate.pkl', 'rb') as f:
    inter = pickle.load(f)

REF_4_1 = Path('results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-V-N3-seed0/train/final_skill/xlsx/SKILL.md').read_text()
REF_5_4 = Path('results/runs/g2b-v8_gpt-5.4/train/final_skill/xlsx/SKILL.md').read_text()


def get_task_desc(task_id):
    """Quick task description for context. Read from input.xlsx filename or dataset."""
    try:
        ds = json.load(open('data/benchmarks/spreadsheetbench/dataset.json'))
        for item in ds:
            if str(item.get('id')) == str(task_id):
                return item['instruction'][:200]
    except: pass
    return f"task_{task_id}"


def llm_judge_2_3a(step_sig, task_desc, skill_md, judge_type):
    """Judge 2: COVERED/NOVEL.  Judge 3a: DOCUMENTED/WARNED/NOVEL."""
    if judge_type == 'J2':
        q = """First briefly paraphrase what the tool call is doing (1 sentence). Then: does this paraphrased action directly follow guidance written in SKILL.md? Consider explicit rules AND worked examples.

Final answer on its own line, exactly one word:
COVERED — if SKILL.md endorses or demonstrates this pattern
NOVEL — if SKILL.md does not address this pattern"""
    else:  # J3a
        q = """First paraphrase the tool call. Then classify its relationship to SKILL.md:
DOCUMENTED — SKILL.md endorses or demonstrates this pattern
WARNED — SKILL.md explicitly warns against this pattern
NOVEL — SKILL.md does not address this pattern at all

Final answer on its own line, exactly one word."""

    system = "You are an expert evaluating whether agent tool calls align with skill guidance. The tool call signature contains tool name + first 200 chars of arguments — you may need to interpret partial arguments charitably."
    user = f"""Tool call: {step_sig}
Task type: {task_desc}
SKILL.md (reference for this backbone):
---
{skill_md[:3000]}
---

{q}"""
    try:
        resp = client.chat.completions.create(
            model='gpt-4.1', temperature=0, max_completion_tokens=200,
            messages=[{'role':'system','content':system},{'role':'user','content':user}]
        )
        out = resp.choices[0].message.content
        last = out.strip().split('\n')[-1].strip().upper()
        for kw in ['COVERED', 'NOVEL', 'DOCUMENTED', 'WARNED']:
            if kw in last: return kw
        return 'PARSE_ERR'
    except Exception as e:
        return f'ERR:{str(e)[:60]}'


def llm_judge_3b(step_sig, task_desc, n_fail, n_pass):
    system = """You are a skill author for an LLM agent system. You are reviewing a tool call that, in observed K-rollout training data, appeared in failed rollouts but not in passing rollouts on the same tasks.

IMPORTANT: You are deciding whether the pattern is a genuine anti-pattern worth documenting in ANY skill, evaluated in vacuum (NOT relative to any specific existing skill artifact). Focus on whether the pattern itself is problematic, regardless of whether some existing skill happens to warn about it or not."""
    user = f"""Tool call: {step_sig}
Task type: {task_desc}
Observed correlation: appeared in {n_fail} failed rollouts, absent from {n_pass} passing rollouts on the same tasks.

Question: First paraphrase the tool call. Then judge: is this a genuine anti-pattern worth documenting, or too situational/noisy?

Final answer on its own line:
SHOULD-WARN — pattern is a real anti-pattern worth documenting
IDIOSYNCRATIC — pattern is too task-specific or noisy to warn about"""
    try:
        resp = client.chat.completions.create(
            model='gpt-4.1', temperature=0, max_completion_tokens=200,
            messages=[{'role':'system','content':system},{'role':'user','content':user}]
        )
        out = resp.choices[0].message.content
        last = out.strip().split('\n')[-1].strip().upper()
        if 'SHOULD-WARN' in last or 'SHOULD_WARN' in last or 'SHOULDWARN' in last:
            return 'SHOULD-WARN'
        if 'IDIOSYNCRATIC' in last:
            return 'IDIOSYNCRATIC'
        return 'PARSE_ERR'
    except Exception as e:
        return f'ERR:{str(e)[:60]}'


def run_judge_2_or_3a(top_sigs, skill_md, backbone_label, judge_type):
    """Run LLM judge on top sigs. Returns counter."""
    from collections import Counter
    results = []
    for i, (sig, count) in enumerate(top_sigs):
        # Extract a task_id from sig context (we don't have direct mapping, use generic)
        task_desc = f"SpreadsheetBench task (signature shared across {count} mixed groups)"
        ans = llm_judge_2_3a(sig, task_desc, skill_md, judge_type)
        results.append((sig[:80], ans))
        print(f"  [{backbone_label} {judge_type} {i+1}/20] {ans}: {sig[:60]}")
    return results


print("=" * 70)
print("GAPV P1 LLM Judges 2 / 3a / 3b")
print("=" * 70)

# Judge 2 per backbone
print("\n## Judge 2-4.1 (positive-advantage COVERED check)")
j2_4_1 = run_judge_2_or_3a(inter['top_pos_4_1'], REF_4_1, '4.1', 'J2')
from collections import Counter
c2_4_1 = Counter(r[1] for r in j2_4_1)
print(f"  Result: {dict(c2_4_1)}")
covered_4_1 = c2_4_1.get('COVERED', 0)
print(f"  COVERED: {covered_4_1}/20 ({covered_4_1*100/20:.0f}%)")

print("\n## Judge 2-5.4 (positive-advantage COVERED check)")
j2_5_4 = run_judge_2_or_3a(inter['top_pos_5_4'], REF_5_4, '5.4', 'J2')
c2_5_4 = Counter(r[1] for r in j2_5_4)
print(f"  Result: {dict(c2_5_4)}")
covered_5_4 = c2_5_4.get('COVERED', 0)
print(f"  COVERED: {covered_5_4}/20 ({covered_5_4*100/20:.0f}%)")

# Judge 2 verdict
print(f"\n## Judge 2 Combined:")
strong_cross = (covered_4_1 >= 8 and covered_5_4 >= 8)
single_strong = ((covered_4_1 >= 10 and covered_5_4 >= 6) or (covered_5_4 >= 10 and covered_4_1 >= 6))
if strong_cross:
    print(f"  STRONG cross-backbone PASS (both ≥8/20)")
elif single_strong:
    print(f"  SINGLE-BACKBONE-STRONG PASS (one ≥10, other ≥6)")
else:
    print(f"  FAIL")
judge_2_pass = strong_cross or single_strong


# Judge 3a
print("\n## Judge 3a-4.1 (negative-advantage NOVEL pool)")
j3a_4_1 = run_judge_2_or_3a(inter['top_neg_4_1'], REF_4_1, '4.1', 'J3a')
c3a_4_1 = Counter(r[1] for r in j3a_4_1)
print(f"  Result: {dict(c3a_4_1)}")
novel_4_1 = c3a_4_1.get('NOVEL', 0)
print(f"  NOVEL: {novel_4_1}/20")

print("\n## Judge 3a-5.4 (negative-advantage NOVEL pool)")
j3a_5_4 = run_judge_2_or_3a(inter['top_neg_5_4'], REF_5_4, '5.4', 'J3a')
c3a_5_4 = Counter(r[1] for r in j3a_5_4)
print(f"  Result: {dict(c3a_5_4)}")
novel_5_4 = c3a_5_4.get('NOVEL', 0)
print(f"  NOVEL: {novel_5_4}/20")

# Judge 3a verdict
strong_cross_3a = (novel_4_1 >= 8 and novel_5_4 >= 8)
single_strong_3a = ((novel_4_1 >= 10 and novel_5_4 >= 6) or (novel_5_4 >= 10 and novel_4_1 >= 6))
print(f"\n## Judge 3a Combined:")
if strong_cross_3a:
    print(f"  STRONG PASS")
elif single_strong_3a:
    print(f"  SINGLE-BACKBONE-STRONG PASS")
else:
    print(f"  FAIL")
judge_3a_pass = strong_cross_3a or single_strong_3a

# Build novel pool for Judge 3b
novel_pool_4_1 = [(sig, j3a_4_1[i][0]) for i, (sig, count) in enumerate(inter['top_neg_4_1']) if j3a_4_1[i][1] == 'NOVEL']
novel_pool_5_4 = [(sig, j3a_5_4[i][0]) for i, (sig, count) in enumerate(inter['top_neg_5_4']) if j3a_5_4[i][1] == 'NOVEL']
combined_novel = novel_pool_4_1 + novel_pool_5_4
print(f"\n## Combined novel pool: {len(combined_novel)} sigs (4.1: {len(novel_pool_4_1)}, 5.4: {len(novel_pool_5_4)})")

# Judge 3b
print("\n## Judge 3b (SHOULD-WARN on novel pool)")
sample = combined_novel[:20]
j3b_results = []
for i, (sig_full, sig_short) in enumerate(sample):
    task_desc = f"SpreadsheetBench task"
    ans = llm_judge_3b(sig_full[0] if isinstance(sig_full, tuple) else sig_full, task_desc, 1, 1)
    j3b_results.append(ans)
    print(f"  [3b {i+1}/{len(sample)}] {ans}: {(sig_full[0] if isinstance(sig_full, tuple) else sig_full)[:60]}")

c3b = Counter(j3b_results)
should_warn = c3b.get('SHOULD-WARN', 0)
total_3b = len(sample)
print(f"\n  SHOULD-WARN: {should_warn}/{total_3b} ({should_warn*100/total_3b if total_3b else 0:.0f}%)")
judge_3b_pass = (should_warn / total_3b >= 0.50) if total_3b > 0 else False
print(f"  PASS (≥50%): {judge_3b_pass}")

# Final verdict
print("\n" + "=" * 70)
print("## FINAL P1 VERDICT")
print("=" * 70)
print(f"Judge 0 (shuffle baseline):  {'PASS' if inter['judge_0']['pass'] else 'FAIL'}")
print(f"Judge 0.5 (length confound): {'PASS' if inter['judge_0_5']['pass'] else 'FAIL'}")
print(f"Judge 1 (Spearman):          {'PASS' if inter['judge_1']['pass'] else 'FAIL'}")
print(f"Judge 2 (positive sanity):   {'PASS' if judge_2_pass else 'FAIL'} (4.1:{covered_4_1}/20, 5.4:{covered_5_4}/20)")
print(f"Judge 3a (novelty pool):     {'PASS' if judge_3a_pass else 'FAIL'} (4.1:{novel_4_1}/20, 5.4:{novel_5_4}/20)")
print(f"Judge 3b (anti-trivial):     {'PASS' if judge_3b_pass else 'FAIL'} ({should_warn}/{total_3b})")

# Verdict tree application
j1_p = inter['judge_1']['pass']
j2_p = judge_2_pass
j3a_p = judge_3a_pass
j3b_p = judge_3b_pass

if j1_p and j2_p and j3a_p and j3b_p:
    case = "A — GAPV validated, proceed to P2 retrain ($25/3h)"
elif j1_p and j2_p and (not j3a_p or not j3b_p):
    case = "B — signal exists but redundant; paper Case B section"
elif j1_p and not j2_p:
    case = "B-edge — flag for re-examination, treat as Case B"
elif not j1_p and (j2_p or j3a_p or j3b_p):
    case = "D — try alt aggregation before declaring dead"
else:
    case = "C — GAPV dead, archive"

print(f"\n→ CASE: {case}")

# Save final
with open('/tmp/gapv_p1_final.json', 'w') as f:
    json.dump({
        'judges': {
            '0': inter['judge_0'],
            '0_5': inter['judge_0_5'],
            '1': inter['judge_1'],
            '2_4_1_covered': covered_4_1,
            '2_5_4_covered': covered_5_4,
            '2_pass': judge_2_pass,
            '3a_4_1_novel': novel_4_1,
            '3a_5_4_novel': novel_5_4,
            '3a_pass': judge_3a_pass,
            '3b_should_warn': should_warn,
            '3b_total': total_3b,
            '3b_pass': judge_3b_pass,
        },
        'case': case,
    }, f, indent=2, default=str)
print(f"\nFinal saved to /tmp/gapv_p1_final.json")
