# G2B-Skill

K-rollout group-dispatch skill self-evolution framework for LLM agents.
Builds on [SkillGrad](https://github.com/wwwhy725/SkillGrad) with a
group-aware diagnoser, structured-claim routing, and structural invariant gating.

## What's different from SkillGrad

| | SkillGrad | G2B-Skill |
| --- | --- | --- |
| Rollouts per task | K=1 | K=4 (configurable) |
| Diagnoser | per-trajectory | per-group, 3-state (all_pass / all_fail / mixed) |
| Patcher routing | single style | 4-tier (procedural_template / mechanism_rewrite / exploration / contrastive) |
| Acceptance | regression-based | regression gate + Fix V structural invariants + anti-wipe revert |

## Supported benchmarks

```
spreadsheetbench (SS)   data/benchmarks/spreadsheetbench/
wikitablequestions (WTQ) data/benchmarks/wikitablequestions/
officeqa                 data/benchmarks/officeqa/
searchqa                 data/benchmarks/searchqa/
livemathbench (LiveMath) data/benchmarks/livemathbench/
```

Each bench is wrapped by an adapter in `bench/`, exposing a uniform protocol
(`load`, `setup_workdir`, `assess`) consumed by the pipeline.

## Setup

### Python environment

`.venv` is a symlink to `../SkillGrad/.venv`. If you don't have SkillGrad
checked out alongside, create a fresh venv:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### API keys

Copy `.env.example` to `.env` and fill in:

```
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://...        # if using proxy / OpenRouter
```

## Usage

### Training (skill evolution)

```bash
.venv/bin/python -m pipeline.g2b_training \
    --bench spreadsheet --model gpt-4.1 \
    --K 4 --batch-size 4 --n-train 32 \
    --batch-schedule fixed-updates --n-iterations 8 \
    --concurrency 2 --batch-seed 0 --training-seed 0 \
    --method g2b-skill --config-tag my-run
```

Output: `results/runs/g2b-skill-<bench>_<model>_<config_tag>/`

Key training-config flags:
- `--K`: rollouts per task per iter (default 4)
- `--n-train`: tasks per iter
- `--n-iterations`: total training iters
- `--enable-sapr`: enable SAPR-minimal adherence judge insert (Phase 4.5)
- `--no-regression-gate`: disable Phase 6 regression gate (ablation)

### Evaluation

```bash
.venv/bin/python -m runners.stream_runner eval \
    --bench spreadsheet \
    --skill-dir results/runs/<run_id>/train/final_skill \
    --output-dir results/runs/<run_id>/eval_r1 \
    --model gpt-4.1 \
    --master-seed 0 --heldout-seed 42 \
    --executor-concurrency 4 --grader-concurrency 1
```

For baselines, point `--skill-dir` at `seeds/` (uses initial seed SKILL.md).

### Templates

`scripts/eval.sh` and `scripts/g2b_train.sh` are minimal launch templates.

## Project structure

```
pipeline/           core training loop + per-phase modules
  g2b_training.py   main entry (g2b-skill method)
  group_execution.py    Phase 1 — K-rollout execution
  group_diagnoser.py    Phase 2 — 3-state classification + per-state cards
  group_momentum.py     Phase 3 — momentum aggregation
  group_patcher.py      Phase 5 — patcher with 4-tier routing
  group_adherence_judge.py  Phase 4.5 — SAPR-minimal (optional)
  regression_gate.py    Phase 6 — regression gate (coreset eval)

runners/            standalone runners
  stream_runner.py  eval + base-trajectory generation

bench/              bench adapters (uniform protocol per bench)
evaluators/         per-bench assessment logic
prompts/            LLM prompt templates per phase
seeds/              initial SKILL.md per bench (from SkillGrad)

scripts/            launch script templates + utilities

data/               raw bench data
  benchmarks/
    spreadsheetbench/   dataset.json + spreadsheet/<id>/
    wikitablequestions/
    officeqa/
    searchqa/
    livemathbench/

results/            run outputs
  runs/<run_id>/
    config.json     run config snapshot
    train/          per-iter snapshots + final_skill
    eval_*/         eval outputs

logs/               training + eval logs

analysis/           experiment analysis notes (badcase studies)
docs/               design docs (FRAMEWORK.md, phase3_momentum_design.md)
```

## Key concepts

**K-rollout group**: N tasks × K rollouts per iter. Each task's K outcomes
classified into one of three states.

**3-state routing**:
- `all_success` — extract regression-anchor procedural template
- `all_failed` — emit `convergence_label` (CONVERGENT / DIVERGENT); patcher applies mechanism rewrite or exploration accordingly
- `mixed` — group-relative advantage attribution; patcher writes contrastive rule

**Fix V structural invariants** (hard caps on skill artifact):
- `SKILL.md ≤ 150 lines`
- `L3 chapters ≤ 12`
- `## Common Pitfalls` must be last H2

Any invariant violation → whole-file revert to pre-patch state.

**Anti-wipe revert**: separately, if patcher output drastically reduces
skill content (wipe pattern), revert.

## Citation

If you use this code, please cite the SkillGrad paper as the foundation:

```bibtex
@article{skillgrad2026,
  title  = {SkillGrad: Optimizing agent skills like gradient descent},
  author = {Wang et al.},
  journal = {arXiv preprint arXiv:2605.27760},
  year   = {2026}
}
```

## License

See `LICENSE`.
