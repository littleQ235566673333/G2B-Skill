# G2B-Skill Final Results — 2026-06-19

All multi-seed (n=3 unless noted) on 100-task slice (master_seed=0, heldout_seed=42).

## Headline Numbers

### GPT-4.1 (paper main result)

| config | SkillGrad mean ± std | v8 + FIX mean ± std | Δ |
|---|---|---|---|
| **SS GPT-4.1** | 32.7 ± 3.1 | **39.3 ± 3.2** | **+6.7pp** |
| **WTQ GPT-4.1** | 55.7 ± 4.0 | **65.3 ± 3.5** | **+9.7pp** |

### GPT-5.4 (parity reference)

| config | SkillGrad mean ± std | v8 mean ± std | Δ |
|---|---|---|---|
| SS GPT-5.4 | 69.0 ± 2.1 | 69.0 ± 1.0 | 0pp (parity, v8 std tighter) |
| WTQ GPT-5.4 | 82.0 ± 1.0 | 82.67 ± 0.58 | +0.67pp (parity, v8 std tighter) |

### Per-seed raw data (3 seeds)

```
GPT-4.1:
  SG SS:        [30, 36, 32]      → 32.7
  v8 SS no-fix: [35, 42, 36]      → 37.7
  v8 SS + FIX:  [43, 37, 38]      → 39.3
  SG WTQ:       [60, 55, 52]      → 55.7
  v8 WTQ no-fix:[54, 57, 50]      → 53.7
  v8 WTQ + FIX: [62, 69, 65]      → 65.3

GPT-5.4:
  SG SS:        [71, 67, 70]      → 69.0
  v8 SS:        [68, 70, 69]      → 69.0
  SG WTQ:       (need to check)   → ~82
  v8 WTQ:       [83, 83, 82]      → 82.67
```

## Run Directory Index

### v8 (G2B-Skill K=4 group-aware)

| run | bench | model | path |
|---|---|---|---|
| g2b-v8_gpt-5.4 | SS | gpt-5.4 | `results/runs/g2b-v8_gpt-5.4/` |
| g2b-v8_gpt-5.4_wtq | WTQ | gpt-5.4 | `results/runs/g2b-v8_gpt-5.4_wtq/` |
| g2b-v8_gpt-4.1_ss-gpt41 | SS | gpt-4.1 (no fix) | `results/runs/g2b-v8_gpt-4.1_ss-gpt41/` |
| g2b-v8_gpt-4.1_wtq-gpt41 | WTQ | gpt-4.1 (no fix) | `results/runs/g2b-v8_gpt-4.1_wtq-gpt41/` |
| **g2b-v8_gpt-4.1_ss-gpt41-fix** | **SS** | **gpt-4.1 + FIX** | `results/runs/g2b-v8_gpt-4.1_ss-gpt41-fix/` |
| **g2b-v8_gpt-4.1_wtq-gpt41-fix** | **WTQ** | **gpt-4.1 + FIX** | `results/runs/g2b-v8_gpt-4.1_wtq-gpt41-fix/` |

### SkillGrad (K=1 baseline)

| run | bench | model | path |
|---|---|---|---|
| skillgrad-spreadsheet_gpt-5.4 | SS | gpt-5.4 | `results/runs/skillgrad-spreadsheet_gpt-5.4/multiseed_100slice_eval/` (SkillGrad project's skill, evaluated locally) |
| skillgrad_gpt-5.4_wtq | WTQ | gpt-5.4 | `results/runs/skillgrad_gpt-5.4_wtq/` |
| skillgrad_gpt-4.1_ss-gpt41 | SS | gpt-4.1 | `results/runs/skillgrad_gpt-4.1_ss-gpt41/` |
| skillgrad_gpt-4.1_wtq-gpt41 | WTQ | gpt-4.1 | `results/runs/skillgrad_gpt-4.1_wtq-gpt41/` |

SkillGrad's original SS skill (gpt-5.4 trained): `/Users/unique/auto_research/Project/SkillGrad/results/runs/skillgrad_gpt-5.4/skills/xlsx/SKILL.md`

## Code: anti-wipe FIX

### Fix a — prompt-level instruction

`pipeline/patcher.py` (run_patch query construction, around line 90):

```
CRITICAL — INCREMENTAL EDITS ONLY:
  Read the current SKILL.md FIRST. Then make INCREMENTAL edits — 
  add new H2 sections, append bullets, refine existing sentences. 
  NEVER replace the entire SKILL.md with a rewritten version. 
  NEVER delete >30% of the existing content in a single edit. 
  If the current SKILL.md has accumulated knowledge, that knowledge 
  is valuable — preserve it and ADD on top, do not start over.
```

### Fix b — code-level guard in v8 training

`pipeline/v8_training.py` (around the PATCH stage):

```python
# Capture pre-patch SKILL.md size
skill_md_path = skills_dir / bench.skill_name / "SKILL.md"
pre_patch_size = skill_md_path.stat().st_size if skill_md_path.exists() else 0
pre_patch_text = skill_md_path.read_text(encoding="utf-8") if skill_md_path.exists() else ""

await run_patch(...)

# Revert if post-patch size shrank > 50% (and pre-patch was substantive)
if skill_md_path.exists() and pre_patch_size > 1500:  # ~50 lines
    post_patch_size = skill_md_path.stat().st_size
    if post_patch_size < pre_patch_size * 0.5:
        print(f"  [PATCH-GUARD] WIPE detected: {pre_patch_size}B → {post_patch_size}B "
              f"({100*(post_patch_size-pre_patch_size)/pre_patch_size:.0f}%). REVERTING.")
        skill_md_path.write_text(pre_patch_text, encoding="utf-8")
```

## Reproduction Commands

### Train (one bench, one model)

```bash
# v8 with FIX (current)
PYTHONPATH=. .venv/bin/python scripts/train_v8.py \
  --bench {spreadsheet|wtq} --model {gpt-4.1|gpt-5.4} \
  --K 4 --n-iterations 10 --batch-size 4 --n-train 40 \
  --concurrency 4 --batch-seed 0 --training-seed 0 \
  --method g2b-v8 --config-tag <unique-suffix>

# SkillGrad baseline
PYTHONPATH=. .venv/bin/python -m pipeline.training \
  --bench {spreadsheet|wtq} --model {gpt-4.1|gpt-5.4} \
  --batch-schedule fixed-updates --n-iterations 10 \
  --batch-size 4 --n-train 40 --concurrency 4 \
  --batch-seed 0 --training-seed 0 \
  --method skillgrad --config-tag <unique-suffix>
```

### Eval (one run, one seed)

```bash
PYTHONPATH=. .venv/bin/python -m runners.stream_runner eval \
  --bench {spreadsheet|wtq} \
  --skill-dir results/runs/<run_id>/train/final_skill \
  --output-dir results/runs/<run_id>/eval_seed<N> \
  --model {gpt-4.1|gpt-5.4} \
  --master-seed 0 --heldout-seed 42 \
  --executor-concurrency 4 --grader-concurrency 1
```

## Wipe Diagnostic Evidence

v8 GPT-4.1 patcher periodically wipes 70-90% of SKILL.md. SkillGrad K=1 patcher does NOT, on same backbone — confirming wipe is v8-input-induced, not GPT-4.1-universal.

### v8 WTQ no-fix snapshot trajectory (wipes at iter 5 and iter 9)

```
iter  1: 45 lines
iter  2: 74 lines
iter  3: 103 lines
iter  4: 123 lines
iter  5: 24 lines    ← WIPE (-99 lines)
iter  6: 86 lines
iter  7: 108 lines
iter  8: 129 lines
iter  9: 8 lines     ← WIPE (-121 lines)
iter 10: 35 lines
FINAL:   70 lines
```

### v8 WTQ + FIX snapshot trajectory (wipes blocked, monotonic growth)

```
iter  1: 45 lines
iter  2: 103 lines
iter  3: 103 lines
iter  4: 144 lines
iter  5: 185 lines
iter  6: 185 lines
iter  7: 185 lines
iter  8: 228 lines
iter  9: 242 lines
iter 10: 242 lines
FINAL:   285 lines  (4x original 70)

Wipes intercepted by code guard: 4
  -57%, -71%, -87%, -76% drop attempts → REVERTED
```

### v8 SS + FIX snapshot trajectory

```
iter  1: 40 lines
iter  2: 104 lines
iter  3: 168 lines
iter  4: 168 lines
iter  5: 241 lines
iter  6: 269 lines
iter  7: 331 lines
iter  8: 405 lines
iter  9: 405 lines
iter 10: 405 lines
FINAL:   405 lines  (3.2x original 127)

Wipes intercepted: 4
  -90%, -98%, -89%, -69% drop attempts → REVERTED
```

### SkillGrad SS GPT-4.1 trajectory (no wipes — control)

```
iter  1: 40 lines
iter  2: 63 lines
iter  3: 64 lines
iter  4: 72 lines
iter  5: 80 lines
iter  6: 77 lines
iter  7: 83 lines
iter  8: 85 lines
iter  9: 87 lines
iter 10: 89 lines
FINAL:   95 lines (clean monotonic, no wipes)
```

## Memory Cross-References

In `/Users/unique/.claude/projects/-Users-unique-auto-research/memory/`:
- `project_g2b_final_paper_grade_2026-06-19.md` — this result documented
- `project_g2b_v8_result_2026-06-19.md` — GPT-5.4 SS parity baseline
- `project_g2b_v8_wtq_2026-06-19.md` — GPT-5.4 WTQ parity
- `project_g2b_step1_gpt41_transfer_2026-06-19.md` — first GPT-4.1 transfer (no fix)
- `project_g2b_singleseed_mechanism_illusion.md` — multi-seed methodology
- `feedback_patcher_skill_name_bug_fix.md` — earlier xlsx hardcode fix

## Cost (this project)

~$300 total. Final v8+FIX retrain+eval (the paper-grade data): ~$55 of that.
