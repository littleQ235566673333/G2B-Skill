"""GAPV P1 analysis per PRE_REGISTRATION_GAPV_P1_v2.1.md (md5: 317aa28e8bf954868db152caf139e118)

Locked spec. Do NOT modify thresholds without opening new pre-reg.
"""
import json
import os
import sys
import asyncio
import statistics
import random
from pathlib import Path
from collections import defaultdict, Counter

# Load env
with open('.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            os.environ[k] = v.strip("'\"")
os.environ['OPENAI_AGENTS_DISABLE_TRACING'] = '1'

# ─── Data loading ──────────────────────────────────────────────────────────

SOURCE_RUNS_4_1 = [
    'results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed0',
    'results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed1',
]
SOURCE_RUN_5_4 = 'results/runs/g2b-skill-spreadsheet_gpt-5.4_SAPR-A5-SS54-N1-seed0'

REF_SKILL_4_1 = 'results/runs/g2b-skill-spreadsheet_gpt-4.1_c-topo-FIX-V-N3-seed0/train/final_skill/xlsx/SKILL.md'
REF_SKILL_5_4 = 'results/runs/g2b-v8_gpt-5.4/train/final_skill/xlsx/SKILL.md'


def extract_tool_calls(jsonl_path):
    if not Path(jsonl_path).exists():
        return []
    sigs = []
    with open(jsonl_path) as f:
        for line in f:
            try:
                e = json.loads(line)
                if e.get('event') != 'tool_call':
                    continue
                content = e.get('content', {})
                if isinstance(content, dict):
                    tool = content.get('tool', '?')
                    args = str(content.get('arguments', ''))[:200]
                    sigs.append(f"{tool}:{args}")
            except Exception:
                pass
    return sigs


def collect_mixed_groups(run_paths, backbone_label):
    """For each mixed-outcome K-rollout group, collect rollouts with their tool-call sigs."""
    if isinstance(run_paths, str):
        run_paths = [run_paths]
    mixed = []
    for run in run_paths:
        for iter_dir in sorted(Path(run).glob('train/iter_*')):
            for group_dir in iter_dir.glob('group_*'):
                if not group_dir.is_dir() or 'diagnose' in group_dir.name:
                    continue
                tid = group_dir.name.replace('group_', '')
                rollouts = []
                for r_dir in sorted(group_dir.glob('r*')):
                    for asmt in r_dir.rglob('assessment_r*.json'):
                        try:
                            a = json.load(open(asmt))
                            passed = bool(a.get('is_correct', False))
                            for jsonl in asmt.parent.glob('exec_r*.jsonl'):
                                sigs = extract_tool_calls(jsonl)
                                rollouts.append({'passed': passed, 'sigs': sigs, 'rollout_idx': r_dir.name})
                                break
                        except Exception:
                            pass
                n_pass = sum(1 for r in rollouts if r['passed'])
                if 0 < n_pass < len(rollouts):
                    mixed.append({
                        'backbone': backbone_label,
                        'task_id': tid,
                        'iter': iter_dir.name,
                        'rollouts': rollouts,
                    })
    return mixed


print("=" * 70)
print("GAPV P1 ANALYSIS — pre-reg v2.1 (md5 317aa28e...)")
print("=" * 70)

mixed_4_1 = collect_mixed_groups(SOURCE_RUNS_4_1, '4.1')
mixed_5_4 = collect_mixed_groups(SOURCE_RUN_5_4, '5.4')
all_mixed = mixed_4_1 + mixed_5_4

print(f"\nData loaded:")
print(f"  4.1 SS mixed groups: {len(mixed_4_1)}")
print(f"  5.4 SS mixed groups: {len(mixed_5_4)}")
print(f"  Combined: {len(all_mixed)} tasks, {sum(len(g['rollouts']) for g in all_mixed)} rollouts")


# ─── Advantage computation ─────────────────────────────────────────────────

def compute_per_group(group):
    """For one task group: per-rollout advantage score (mean-normalized)."""
    pass_sigs_union = set()
    fail_sigs_union = set()
    for r in group['rollouts']:
        if r['passed']:
            pass_sigs_union |= set(r['sigs'])
        else:
            fail_sigs_union |= set(r['sigs'])

    for r in group['rollouts']:
        adv_sum = 0
        for s in r['sigs']:
            if s in pass_sigs_union and s not in fail_sigs_union:
                adv_sum += 1
            elif s in fail_sigs_union and s not in pass_sigs_union:
                adv_sum -= 1
        r['advantage_score'] = adv_sum / max(len(r['sigs']), 1)
        r['n_steps'] = len(r['sigs'])
    return group


for g in all_mixed:
    compute_per_group(g)

all_rollouts = [r for g in all_mixed for r in g['rollouts']]
print(f"\nAdvantage scores computed for {len(all_rollouts)} rollouts.")
print(f"  Range: [{min(r['advantage_score'] for r in all_rollouts):.3f}, "
      f"{max(r['advantage_score'] for r in all_rollouts):.3f}]")


# ─── Judge 0: shuffle baseline ─────────────────────────────────────────────

def spearman_r(xs, ys):
    """Compute Spearman r and approx p-value."""
    from scipy import stats
    return stats.spearmanr(xs, ys)


advantages = [r['advantage_score'] for r in all_rollouts]
outcomes = [1 if r['passed'] else 0 for r in all_rollouts]
lengths = [r['n_steps'] for r in all_rollouts]

random.seed(42)
shuffled_rs = []
for _ in range(10):
    shuffled = outcomes[:]
    random.shuffle(shuffled)
    r_corr, _ = spearman_r(advantages, shuffled)
    shuffled_rs.append(abs(r_corr))

shuffle_mean = statistics.mean(shuffled_rs)
shuffle_max = max(shuffled_rs)
print(f"\n## Judge 0 (shuffle baseline, 10 perms):")
print(f"  Mean |r|: {shuffle_mean:.3f}, Max |r|: {shuffle_max:.3f}")
judge_0_pass = (shuffle_mean < 0.2) and (shuffle_max < 0.30)
print(f"  PASS condition: mean<0.2 AND max<0.30 → {'PASS' if judge_0_pass else 'FAIL'}")


# ─── Judge 0.5: length confound gate ───────────────────────────────────────

r_length, p_length = spearman_r(lengths, outcomes)
print(f"\n## Judge 0.5 (length-outcome correlation):")
print(f"  r(length, outcome) = {r_length:.3f}, p = {p_length:.4f}")

# Partial correlation: r(advantage, outcome | length)
def partial_corr_spearman(x, y, z):
    """Partial Spearman r(x, y | z) via residualization on ranks."""
    from scipy import stats
    import numpy as np
    x_rank = stats.rankdata(x)
    y_rank = stats.rankdata(y)
    z_rank = stats.rankdata(z)
    # Linear residualize x and y on z
    z_centered = z_rank - z_rank.mean()
    bx = np.dot(x_rank - x_rank.mean(), z_centered) / np.dot(z_centered, z_centered)
    by = np.dot(y_rank - y_rank.mean(), z_centered) / np.dot(z_centered, z_centered)
    rx = x_rank - bx * z_centered - x_rank.mean()
    ry = y_rank - by * z_centered - y_rank.mean()
    # Pearson of residuals = partial Spearman approximation
    return stats.pearsonr(rx, ry)

partial_r, partial_p = partial_corr_spearman(advantages, outcomes, lengths)
print(f"  Partial r(advantage, outcome | length) = {partial_r:.3f}, p = {partial_p:.4f}")
length_confound = abs(r_length) >= 0.30
print(f"  Length confound detected (|r1|≥0.3): {length_confound}")
if length_confound:
    partial_ok = (abs(partial_r) >= 0.30) and (partial_p < 0.05)
    print(f"  Partial confound-controlled r ≥ 0.30 AND p < 0.05: {partial_ok}")
    judge_0_5_pass = partial_ok
else:
    judge_0_5_pass = True
    print(f"  No length confound — Judge 1 proceeds normally")


# ─── Judge 1: Spearman correlation ─────────────────────────────────────────

r_combined, p_combined = spearman_r(advantages, outcomes)
adv_4_1 = [r['advantage_score'] for g in mixed_4_1 for r in g['rollouts']]
out_4_1 = [1 if r['passed'] else 0 for g in mixed_4_1 for r in g['rollouts']]
adv_5_4 = [r['advantage_score'] for g in mixed_5_4 for r in g['rollouts']]
out_5_4 = [1 if r['passed'] else 0 for g in mixed_5_4 for r in g['rollouts']]

r_4_1, p_4_1 = spearman_r(adv_4_1, out_4_1)
r_5_4, p_5_4 = spearman_r(adv_5_4, out_5_4)

print(f"\n## Judge 1 (Spearman correlation):")
print(f"  Combined N={len(advantages)}: r = {r_combined:.3f}, p = {p_combined:.4f}")
print(f"  4.1 SS N={len(adv_4_1)}: r = {r_4_1:.3f}, p = {p_4_1:.4f}")
print(f"  5.4 SS N={len(adv_5_4)}: r = {r_5_4:.3f}, p = {p_5_4:.4f}")

cond_A = (r_combined >= 0.40) and (p_combined < 0.01)
cond_B = ((r_4_1 >= 0.40) and (p_4_1 < 0.01)) or ((r_5_4 >= 0.40) and (p_5_4 < 0.01))
strong_bb_idx = '4.1' if r_4_1 >= r_5_4 else '5.4'
other_r = r_5_4 if strong_bb_idx == '4.1' else r_4_1
cond_C = (other_r >= 0.20) and ((other_r > 0) == (r_combined > 0))

judge_1_pass = cond_A and cond_B and cond_C and judge_0_5_pass
print(f"  Condition A (combined r≥0.4 + p<0.01): {cond_A}")
print(f"  Condition B (one backbone r≥0.4 + p<0.01): {cond_B}")
print(f"  Condition C (other backbone r≥0.2 same direction): {cond_C}")
print(f"  Judge 0.5 gate ok: {judge_0_5_pass}")
print(f"  Judge 1 PASS: {judge_1_pass}")


# ─── Top-20 step extraction per backbone ───────────────────────────────────

def top_n_signatures(mixed_groups, sign, n=20):
    """Return top-N unique step signatures by frequency of advantage=sign."""
    counter = Counter()
    for g in mixed_groups:
        pass_sigs_u = set(s for r in g['rollouts'] if r['passed'] for s in r['sigs'])
        fail_sigs_u = set(s for r in g['rollouts'] if not r['passed'] for s in r['sigs'])
        if sign == +1:
            for s in pass_sigs_u - fail_sigs_u:
                counter[s] += 1
        elif sign == -1:
            for s in fail_sigs_u - pass_sigs_u:
                counter[s] += 1
    return counter.most_common(n)


top_pos_4_1 = top_n_signatures(mixed_4_1, +1, 20)
top_neg_4_1 = top_n_signatures(mixed_4_1, -1, 20)
top_pos_5_4 = top_n_signatures(mixed_5_4, +1, 20)
top_neg_5_4 = top_n_signatures(mixed_5_4, -1, 20)

print(f"\n## Top-N step signatures extracted:")
print(f"  4.1 SS top-20 +advantage: {len(top_pos_4_1)}")
print(f"  4.1 SS top-20 -advantage: {len(top_neg_4_1)}")
print(f"  5.4 SS top-20 +advantage: {len(top_pos_5_4)}")
print(f"  5.4 SS top-20 -advantage: {len(top_neg_5_4)}")


# Save intermediate so we can run LLM judges in next step
import pickle
intermediate = {
    'judge_0': {'mean': shuffle_mean, 'max': shuffle_max, 'pass': judge_0_pass},
    'judge_0_5': {'r_length': r_length, 'partial_r': partial_r, 'partial_p': partial_p,
                  'confound': length_confound, 'pass': judge_0_5_pass},
    'judge_1': {'r_combined': r_combined, 'p_combined': p_combined,
                'r_4_1': r_4_1, 'p_4_1': p_4_1,
                'r_5_4': r_5_4, 'p_5_4': p_5_4,
                'cond_A': cond_A, 'cond_B': cond_B, 'cond_C': cond_C, 'pass': judge_1_pass},
    'top_pos_4_1': top_pos_4_1,
    'top_neg_4_1': top_neg_4_1,
    'top_pos_5_4': top_pos_5_4,
    'top_neg_5_4': top_neg_5_4,
    'all_mixed': all_mixed,
}
with open('/tmp/gapv_p1_intermediate.pkl', 'wb') as f:
    pickle.dump(intermediate, f)
print(f"\nIntermediate saved to /tmp/gapv_p1_intermediate.pkl")
print("Next: LLM judges 2/3a/3b (run gapv_p1_llm_judges.py)")
