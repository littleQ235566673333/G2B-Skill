# RSM Tier 0 — anti-wipe behavior characterization

**Goal**: determine whether anti-wipe is over-protective on at least some
events ("误杀 stale_cleanup"), neutral, or correctly intercepts destructive
content. Pure measurement; no LLM-judge in the loop.

**Decision rule (dual)**:
1. **Existence**: at least one event in the spot-check is verdict
   `stale_cleanup` or `ambiguous`.
2. **Cluster**: ≥30% of events fall in `stale_cleanup` or `ambiguous`.

If both → Tier 1 (rule-level provenance + per-rule revert decision).
If either fails → drop RSM line.

**Sample stratification** (must split, not pool):

| stratum | source | anti_wipe_engaged | what we measure |
|---|---|---|---|
| **A. Intercepted** | v8 + FIX runs (SS/WTQ/OfficeQA + 4.1) | yes | did the guard correctly intercept? |
| **B. Unintervened** | SG runs (OfficeQA + 4.1) | no | natural experiment — what does an unintercepted wipe do? |

Stratum B is the harder counterfactual — if next-iter score *increases*
after a B-event, anti-wipe is over-protective; if it *decreases*, the FIX's
9 interceptions in Stratum A are likely correct.

**Known limitation (Tier 0 cannot resolve)**: `next_iter_pass_count_delta`
is observational, not counterfactual. The next iter's batch may be
unrelated to the deleted rule's content, in which case the delta is
noise. We record `next_iter_batch_task_ids` so we can spot-check whether
the batch was even relevant; we do not claim causal lift from delta alone.

---

## Per-event template (one row per wipe event)

```yaml
- run_id: <e.g. g2b-v8_gpt-4.1_ss-gpt41-fix>
  iter: <int>
  anti_wipe_engaged: yes | no
  stratum: A | B

  # Quantitative (auto-filled by script)
  pre_lines: <int>
  post_lines: <int>           # post-revert if engaged; post-wipe if not
  drop_pct: <float>           # (post - pre) / pre, signed
  pre_size_bytes: <int>
  post_size_bytes: <int>

  # Content (auto-filled where possible; manual top-3 deleted)
  deleted_rule_texts:
    - rule: "<L2 / L3 sentence>"
      originating_case_id_if_recoverable: <case_id or "unknown">
    - rule: "..."
      originating_case_id_if_recoverable: ...
    - rule: "..."
      originating_case_id_if_recoverable: ...

  # Causal context (auto-filled by script — for spot-check interpretation only)
  next_iter_batch_task_ids: [<id>, <id>, ...]
  next_iter_pass_count: <int>
  prev_iter_pass_count: <int>
  next_iter_pass_count_delta: <signed int>

  # MANUAL FIELDS (you fill during spot-check)
  my_verdict: destructive | stale_cleanup | ambiguous
  verdict_notes: |
    <brief why — what was deleted, was it useful, was the next-iter batch
    related to the deleted content. delta is observational, don't over-claim.>
```

---

## Verdict definitions

- **destructive**: deleted content was useful (covered known failure
  modes, contained domain knowledge an executor would need). Anti-wipe
  intervention was correct.
- **stale_cleanup**: deleted content was redundant, contradicted by newer
  rules, or covered a failure mode that's no longer hit. Anti-wipe
  intervention was over-protective; rule-level decision would have
  preserved the new, deleted the old.
- **ambiguous**: deleted content's value is unclear without more context;
  next-iter delta is dominated by unrelated tasks; or the deleted rules
  mix useful + redundant.

When in doubt → ambiguous. Don't force a binary.

---

## Files this analysis will produce

- `analysis/rsm_tier0/template.md` — this file (spec)
- `analysis/rsm_tier0/events_auto.yaml` — quantitative auto-fill output
- `analysis/rsm_tier0/events_filled.yaml` — same + manual `my_verdict`
- `analysis/rsm_tier0/REPORT.md` — final tally + decision per dual rule
