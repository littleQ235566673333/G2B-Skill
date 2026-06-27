"""P0.1: GAPV robustness check.
Re-judge top-20 negative-advantage steps with gpt-5.4 as second judge.
Compare to gpt-4.1 (original). If disagreement is high, the 0/40 NOVEL number isn't robust."""
import json, os, pickle
from pathlib import Path
from collections import Counter

with open('.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            os.environ[k] = v.strip("'\"")

from openai import OpenAI
client = OpenAI()

with open('/tmp/gapv_p1_intermediate.pkl', 'rb') as f:
    inter = pickle.load(f)

REF_4_1 = Path('results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-V-N3-seed0/train/final_skill/xlsx/SKILL.md').read_text()
REF_5_4 = Path('results/runs/g2b-v8_gpt-5.4/train/final_skill/xlsx/SKILL.md').read_text()


def judge_3a(step_sig, skill_md, model):
    system = "You are an expert evaluating whether agent tool calls align with skill guidance. The tool call signature contains tool name + first 200 chars of arguments — you may need to interpret partial arguments charitably."
    user = f"""Tool call: {step_sig}
Task type: SpreadsheetBench task (signature shared across mixed groups)
SKILL.md (reference for this backbone):
---
{skill_md[:3000]}
---

First paraphrase the tool call. Then classify its relationship to SKILL.md:
DOCUMENTED — SKILL.md endorses or demonstrates this pattern
WARNED — SKILL.md explicitly warns against this pattern
NOVEL — SKILL.md does not address this pattern at all

Final answer on its own line, exactly one word."""
    try:
        resp = client.chat.completions.create(
            model=model, temperature=0, max_completion_tokens=200,
            messages=[{'role':'system','content':system},{'role':'user','content':user}]
        )
        out = resp.choices[0].message.content
        last = out.strip().split('\n')[-1].strip().upper()
        for kw in ['DOCUMENTED', 'WARNED', 'NOVEL']:
            if kw in last:
                return kw, out
        return 'PARSE_ERR', out
    except Exception as e:
        return f'ERR', str(e)


print("=" * 70)
print("P0.1: GAPV robustness check — gpt-5.4 as second judge")
print("=" * 70)

agreements = []
disagreements = []
all_results = []

# Re-judge all top-20 negative-advantage steps on each backbone
for backbone, top_neg, skill in [('4.1', inter['top_neg_4_1'], REF_4_1),
                                   ('5.4', inter['top_neg_5_4'], REF_5_4)]:
    print(f"\n## Backbone {backbone} ({len(top_neg)} negative-advantage steps)")
    for i, (sig, count) in enumerate(top_neg):
        # First judge was gpt-4.1; both classified as DOCUMENTED or WARNED (none NOVEL)
        # Now re-judge with gpt-5.4
        ans_54, raw_54 = judge_3a(sig, skill, 'gpt-5.4')
        # Re-judge with gpt-4.1 too for sanity (some calls flake)
        ans_41, raw_41 = judge_3a(sig, skill, 'gpt-4.1')
        agree = (ans_41 == ans_54)
        # Did either change to NOVEL?
        any_novel = (ans_41 == 'NOVEL') or (ans_54 == 'NOVEL')

        all_results.append({
            'backbone': backbone, 'sig': sig[:80],
            'gpt41': ans_41, 'gpt54': ans_54,
            'agree': agree, 'any_novel': any_novel
        })
        if agree:
            agreements.append((backbone, sig[:60], ans_41))
        else:
            disagreements.append((backbone, sig[:60], ans_41, ans_54))
        marker = "✓" if agree else "✗"
        novel_marker = " ⚠NOVEL" if any_novel else ""
        print(f"  [{i+1:2d}/20] {marker} gpt-4.1={ans_41:11s} gpt-5.4={ans_54:11s}{novel_marker}")

# Summary
total = len(all_results)
n_agree = sum(1 for r in all_results if r['agree'])
n_novel_any = sum(1 for r in all_results if r['any_novel'])
n_novel_both = sum(1 for r in all_results if r['gpt41'] == 'NOVEL' and r['gpt54'] == 'NOVEL')

print()
print("=" * 70)
print("ROBUSTNESS VERDICT")
print("=" * 70)
print(f"Total steps re-judged: {total}")
print(f"Inter-model agreement (gpt-4.1 vs gpt-5.4): {n_agree}/{total} = {n_agree*100/total:.1f}%")
print(f"At least one judge classified as NOVEL: {n_novel_any}/{total} ({n_novel_any*100/total:.1f}%)")
print(f"Both judges classified as NOVEL: {n_novel_both}/{total} ({n_novel_both*100/total:.1f}%)")
print()

# Original result was 0/40 NOVEL on gpt-4.1
# Robustness: if both models agree it's not NOVEL, the 0/40 claim is robust
# If gpt-5.4 finds some NOVEL → 0/40 was gpt-4.1-specific leniency
print("## Interpretation:")
if n_novel_any == 0:
    print("  → 0/40 NOVEL claim ROBUST. Both gpt-4.1 and gpt-5.4 agree no novel.")
    print("    Case B verdict stands. Paper claim defensible.")
elif n_novel_any <= 4:
    print(f"  → 0/40 NOVEL slightly OVER-CLAIMED. gpt-5.4 finds {n_novel_any}/40 novel.")
    print(f"    Case B verdict mostly stands but with caveat: '≤10% novel rate'.")
elif n_novel_any <= 10:
    print(f"  → 0/40 NOVEL CONTAMINATED. gpt-5.4 finds {n_novel_any}/40 novel (≤25%).")
    print(f"    Case B verdict needs softening: 'novelty rate disputed across judges'.")
else:
    print(f"  → 0/40 NOVEL NOT ROBUST. gpt-5.4 finds {n_novel_any}/40 novel (>25%).")
    print(f"    Case B verdict UNSTABLE. Need stricter Judge 3a prompt + re-run.")

# Save
with open('/tmp/gapv_p1_robustness.json', 'w') as f:
    json.dump({
        'total': total,
        'agreement_rate': n_agree / total,
        'any_novel_rate': n_novel_any / total,
        'both_novel_rate': n_novel_both / total,
        'all_results': all_results,
    }, f, indent=2)
print(f"\nSaved to /tmp/gapv_p1_robustness.json")
