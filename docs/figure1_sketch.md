# Figure 1 Sketch — G2B-Skill vs SkillGrad vs SkillRL

> Status: ASCII draft. Iterate here; promote to TikZ / matplotlib once contribution narrative is locked.

## Design intent

**One question, three corners.** Every panel must answer the same question:
*"Where does the within-task multi-rollout signal go, and what gates it before landing?"*

Reviewer should be able to look at this figure for 30 seconds and walk away with:
1. SkillGrad has no group structure; the signal is single-trace + cross-version.
2. SkillRL has the group structure but routes the GRPO advantage to LLM weights; skills come from a separate teacher channel.
3. G2B-Skill has the group structure and routes the GRPO advantage **directly to the skill artifact**.

The differentiator is not "what data" but "where the signal lands."

---

## Layout v1 — three vertical panels, shared y-axis

```
                  SkillGrad              SkillRL               G2B-Skill (ours)
                  ─────────              ───────               ────────────────

  Signal          ┌─────────────┐       ┌─────────────┐        ┌─────────────┐
  source          │ N tasks × 1 │       │ N tasks ×   │        │ N tasks ×   │
                  │ trajectory  │       │ G=8 rollouts│        │ K rollouts  │
                  │             │       │ (within-task│        │ (within-task│
                  │ + base traj │       │  same-skill)│        │  same-skill)│
                  │ contrast    │       │             │        │             │
                  │ (cross-ver) │       │             │        │             │
                  └──────┬──────┘       └──────┬──────┘        └──────┬──────┘
                         │                     │                      │
                         │              GRPO advantage          group-relative
                         │              A_i = (R_i − μ)/σ      advantage routed
                         │                     │                  to claims
                         │                     │                      │
                         ▼              ┌──────┴──────┐               ▼
  Routing /      ┌─────────────┐       │             │        ┌─────────────┐
  update         │ free-form   │       ▼             ▼        │ structured  │
  target         │ diagnoser   │   ┌────────┐  ┌──────────┐   │ claim →     │
                 │ → momentum  │   │  LLM   │  │  skill   │   │ 4-tier route│
                 │ → patcher   │   │ WEIGHTS│  │ (teacher │   │ {core/aux/  │
                 │ (LLM rewrite│   │ (PPO   │  │ on failed│   │  pending/   │
                 │  text)      │   │ clipped│  │  vali-   │   │  discard}   │
                 │             │   │ obj.)  │  │ dations) │   │             │
                 └──────┬──────┘   └────────┘  └─────┬────┘   └──────┬──────┘
                        │              ▲              │               │
                        │              │              │               │
                        │              └──── decoupled┘               │
                        │              (NO group-relative              │
                        │               signal to skill)               │
                        │                                              │
                        ▼                            ▼                 ▼
  Acceptance     ┌─────────────┐                ┌──────────┐    ┌─────────────┐
                 │ EVERY patch │                │ skills:  │    │ regression- │
                 │ accepted    │                │ uncondi- │    │ aware gate  │
                 │ (no gate)   │                │ tionally │    │ on group-   │
                 │             │                │ added    │    │ batch evi-  │
                 │ → silent    │                │          │    │ dence pool  │
                 │   regression│                │ → mono-  │    │             │
                 │   observed  │                │ tonic    │    │ → forward-  │
                 │   (our base-│                │ growth   │    │ only, no CF │
                 │   line run) │                │ 55→100   │    │ replay      │
                 └─────────────┘                └──────────┘    └─────────────┘

  GPU?           ✗ (API)                        ✓ 8× H100 30h    ✗ (API)
  Skill format   markdown L1/L2/L3              JSON 2-tier      markdown L1/L2/L3+case
  Bench          SpreadsheetBench Verified +    ALFWorld +       (TBD; default
                 WikiTableQuestions             WebShop + 7 QA   SpreadsheetBench)
```

---

## Visual emphasis (when this becomes a real figure)

- **Bold the green arrow**: the path from "K rollouts within-task" → "skill artifact" in G2B-Skill panel. That's the contribution-1 visual hook.
- **Gray out the dashed "decoupled" indicator** in the middle (SkillRL) panel: it's the visual articulation of "group-relative signal exists but does not touch skill." This is the corner G2B-Skill is *not* in.
- **Red strikethrough on "EVERY patch accepted"** in SkillGrad panel — paired with a small inset showing iter 6→7→8 silent regression curve from our baseline run. Caption: "no gate, regression observed in our reproduction."
- **Add a small comparison table** under the figure for the (Skill format / Bench / GPU) row — side-text not in the main figure body.

---

## Variants to consider

**v1 (above)**: 3 vertical panels, signal flows top-to-bottom. Best for clear differentiation.

**v2** (alternative): 1 figure with a 2D positioning chart:
```
                              skill update gate ↑
                              (regression-aware) │
                                                 │
                                       G2B  ●────┤
                                                 │
                                                 │
                              ───────────────────┼──────────── group-relative
                                                 │            signal lands on:
                              SkillGrad  ●       │
                                                 │      ● SkillRL (weights)
                                                 │
                              (no gate)          │
                                                 ↓
```
Use only if reviewers complain v1 is too dense.

**v3** (alternative): SkillRL framing as a "missing edge" — show skill update channel as a dotted edge bypassing GRPO, with G2B-Skill drawing the solid edge. Best for a poster, probably too clever for paper.

---

## What this figure does NOT show (and shouldn't try to)

- L1/L2/L3 progressive disclosure structure of the skill — that's a separate diagram (Figure 2 candidate).
- The Phase 4 routing threshold details — that's a separate sub-figure or table.
- Curriculum mechanism — out of contribution scope.
- The structured-claim schema slot list — appendix material.

Keep Figure 1 to **the differentiator only**: signal source, routing target, acceptance.

---

## Open questions (decide before promoting to vector)

1. Should the SkillGrad panel show the silent-regression curve inset, or save that for a later Section-3 motivation figure? (Inset is rhetorically strong but visually noisy.)
2. Should we include a fourth panel for "ablation: K=1 G2B" to show the within-task group structure is what's doing the work? Or save that for the experiment section?
3. Color-coding: monochromatic (paper-friendly, color-blind safe) or accent-color on the routing target box?
4. Should the figure caption explicitly call out "we simulate GRPO in text space" or save for the abstract / contribution paragraph?

---

## TODO before promoting

- [ ] Lock contribution narrative (done in framework doc §A v4)
- [ ] Decide v1 vs v2 vs v3 layout
- [ ] Lock bench list (waiting on Q3 discussion)
- [ ] Inset: silent-regression curve from baseline run (data exists at `Project/SkillGrad/results/runs/skillgrad_gpt-5.4/train/training_results.json`)
- [ ] Caption draft (≤80 words)
