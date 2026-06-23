# C-Topology v3 Placement × Style Disentangle — Final Report

**Date**: 2026-06-21 (post-v2 ablation)
**Protocol**: `protocol_v3_placement_style.md` (frozen pre-eval)
**Cost**: $28.39 (under $30 cap; no multi-seed follow-up triggered)

## TL;DR

**Verdict: SKILL.md injection structurally bounded** — neither rule
placement (top / middle / end) nor rule style/anchoring (bare /
Why-anchored / process-voice) produces measurable outcome lift on
OQA-5.4 stable-v8-fail cases. v2 outcome null is robust to all three
mechanism fixes I hypothesized.

**Stronger reading**: even when rules ARE more thoroughly read by the
executor (avg-hit grep up +3-4 in Pb/Pc), outcome stays flat. This
points to **capability ceiling, not rule-delivery**.

**C-topology line: firmly future work**. No patcher prompt redesign at
the SKILL.md-content level recovers OQA-5.4 stable-v8-fail outcome.

## Result matrix

### Outcome layer

| condition | description | pass / 5 |
|---|---|---|
| Pa | end + bare imperative (= v2 baseline) | 1 / 5 |
| Pb | middle (## Function Rules before Common Pitfalls) + bare | 1 / 5 |
| Pc | top (## Critical Avoidances after frontmatter) + bare | 1 / 5 |
| Sb | end + Why-anchored (generalized causal "Why:" sentence) | 0 / 5 |
| Sc | end + process-style ("Before X, verify Y") | 0 / 5 |

P range: 1-1-1 (Pa=Pb=Pc, no movement). S range: 1-0-0 (Sb/Sc slight regression).

### Behavior layer (avoid_signal grep)

```
cond   oqa-112    oqa-118    oqa-130    oqa-14     oqa-35     avg     any_hit_count
Pa     0          0          0          8          8          3.2     2/5
Pb     0          0          4          22         10         7.2     3/5
Pc     0          0          1          26         8          7.0     3/5
Sb     0          0          0          24         8          6.4     2/5
Sc     0          0          2          8          8          3.6     3/5
```

- **avg hits**: Pb (7.2) and Pc (7.0) show ~2x v2-baseline avg hits.
  Placement at middle/top DOES surface rules more in trace.
- **any_hit_count**: Pb / Pc / Sc each gain +1 case over Pa (3 vs 2). Pre-committed threshold was ≥+2 — not met.

## Pre-committed verdict application

| P movement (any of Pb/Pc ≥ Pa + 2) | S movement (any of Sb/Sc ≥ Pa + 2) | verdict |
|---|---|---|
| **No** (Pb/Pc = 3 vs Pa = 2) | **No** (Sb = 2, Sc = 3) | **"SKILL.md injection structurally bounded"** |

Per pre-frozen rule: this is the strongest negative-mechanism cell. No
patcher prompt fix at the SKILL.md content level recovers outcome on
OQA-5.4 stable-v8-fail. C-topology line firmly future work.

Multi-seed follow-up: NOT triggered (no condition won).

## Mechanism interpretation

### What v3 ruled OUT

- ① attention dilution as primary cause: top + middle placements both fail to lift outcome despite 2x avg-hit boost
- ⑤ anchoring as primary cause: Why-anchored Sb regressed (0/5)
- ③ style as primary cause: process-voice Sc also regressed
- "Combined fix" (placement + style + anchoring): if individually null, joint also null

### What v3 leaves OPEN

- **Capability ceiling**: agent reads rules more (Pb/Pc avg hits up) but still can't pass. Suggests the v8 model on OQA-5.4 stable_fail can't execute the rule's prescription correctly even when surfaced.
- **OQA-5.4 specific**: untested whether placement/style would matter on benches where v8 has more capability headroom (e.g., SS / WTQ on weaker backbone).
- **Patcher-time changes** (not SKILL.md-time): unverified whether training-time rule integration into v8's process-skill content has different effect from post-hoc append.

### Why the regressions in Sb / Sc

Speculative — not pre-committed. The Why-anchored and process-style rules are LONGER (more tokens) than bare imperatives. They might compete with v8's existing process-style skill content (Strategy that works well, Read tables and series) for executor attention, while bare imperatives might be quietly ignored without disrupting v8's flow. So adding integrated/anchored rules can be net-negative if the integration is imperfect.

If true, this argues that **integrated rule injection requires reorganizing the entire skill, not just appending one section** — which means real C-topology requires patcher-time training change, not just SKILL.md-edit.

## Cost & methodology notes

- Pre-registered protocol frozen pre-eval; no rule edits, case swaps, or threshold re-tuning during/after run
- Multi-seed follow-up gate: only on positive result; not triggered
- 25 unique runs (5 conditions × 5 cases × 1 seed); $28.39 within $30 cap
- Avg per-run cost ~$1.14 — higher than v2's ~$0.50 because v3 ran same long-context cases that have heavy reasoning
- All 5 conditions ran without rate-limit hangs (unlike v2 Branch 3)

## What this means for paper

Combined with v2 multi-seed result and v1 ablation:

| layer | what we know |
|---|---|
| v1 (5 case × 1 seed, hand-tailored rules) | behavior signal 4/5 vs 1/5 — sample-dependent |
| v2 (10 case × 5 seed, cross-bench tailored) | mean Δ −0.04, CI [−0.10, 0.00], rule_executed 4/10, rule_ignored 5/10 |
| v3 (5 case × 5 conditions × 1 seed) | placement + style fixes don't recover; all conditions flat outcome; behavior surface rate increases without outcome lift |

**Combined story**: tailored negative rules at SKILL.md-edit level cannot
fix OQA-5.4 stable-v8-fail. Each progressively stronger ablation keeps
returning flat-outcome verdicts. Three independent attempts (v1 hand-write,
v2 multi-seed, v3 disentangle) converge on the same conclusion.

This is a **clean negative finding** for paper:
- Specific intervention class (post-training SKILL.md negative-rule edits) does not lift OQA-5.4 stable-fail outcome
- Mechanism gap localized: rule-content-vs-executor-capability is the bottleneck, not rule-delivery / placement / framing
- Paper recommendation: weak-backbone amplification (SS/WTQ +6.7/+9.7) remains the headline; OQA-5.4 + C-topology is **future work that requires patcher-time changes, not SKILL.md-time**

## Files

- `analysis/c_topo_ablation/protocol_v3_placement_style.md` (frozen)
- `analysis/c_topo_ablation/build_v3_skills.py` (5 skill variants)
- `analysis/c_topo_ablation/v3_skills/{Pa,Pb,Pc,Sb,Sc}/officeqa/SKILL.md`
- `analysis/c_topo_ablation/run_v3_ablation.py`, `grep_v3.py`
- `analysis/c_topo_ablation/v3_results/results.json` (25 runs)
- `analysis/c_topo_ablation/v3_grep_summary.json`
- `analysis/c_topo_ablation/REPORT_v3.md` (this file)

Cumulative C-topology investigation cost: v1 $20 + v2 $120 + v3 $28 = **$168**.
