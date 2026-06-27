#!/usr/bin/env python3
"""Simplified mechanism ablation — direct chat.completions, no Agent framework.

The Agent framework uses Responses API which OpenRouter doesn't support.
For this ablation we only need the patcher LLM's text response, not the
full tool-call loop.
"""
import os
from pathlib import Path
import httpx
from openai import OpenAI

# Load patcher prompt
import importlib.util
spec = importlib.util.spec_from_file_location("group_patcher_prompts",
    "prompts/group_patcher.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
PROMPT = m.GROUP_PATCHER_PROMPT

# Load supporting files
ITER8 = Path("results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed1/train/iter_8")
SKILLS = Path("results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed1/skills/xlsx")

cards = (ITER8 / "batch_diagnostic_cards.md").read_text()
overlay = (ITER8 / "momentum_overlay.md").read_text()
record_path = Path("results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed1/train/momentum_memory.md")
record = record_path.read_text() if record_path.exists() else ""
pending_path = Path("results/runs/g2b-skill-spreadsheet_gpt-4.1_SAPR-A5-N2-seed1/train/pending_pool.md")
pending = pending_path.read_text() if pending_path.exists() else ""
skill_md = (SKILLS / "SKILL.md").read_text()
adh = (ITER8 / "adherence_summary.md").read_text()

# Truncate big files to fit context
def trim(s, n): return s[:n] + "\n...(truncated)" if len(s) > n else s

def build_query(include_adherence: bool):
    q = f"""This is iteration 8 (ABLATION REPLAY).

## Inputs (read inline; do NOT read_file)

### Group cards (batch_diagnostic_cards.md)
{trim(cards, 6000)}

### Momentum overlay
{trim(overlay, 3000)}

### Pattern record
{trim(record, 2000)}

### Pending pool
{trim(pending, 1000)}

### Current SKILL.md
{trim(skill_md, 4000)}

## Output instruction
Output ONLY your "Routing Decisions Table" + "Patch Actions" sections.
For each routed pattern, specify: route + which H2 section to edit OR
new H2 to add. Do NOT write file contents. Be concise."""
    if include_adherence:
        q += f"\n\n## Adherence signal (SAPR-minimal)\n\n{adh}\n\n**Patcher instruction (generic):** when proposing patches, prioritize the LOW_ADH_ON_FAIL and HIGH_ADH_ON_FAIL flagged rules above. For LOW_ADH_ON_FAIL, edit prominence/wording/position only — do NOT rewrite content. For HIGH_ADH_ON_FAIL, edit content/decision logic — do NOT touch prominence. Apply this signal across all flagged rules; do not single out any specific rule a priori."
    return q

_api_key = os.environ.get("OPENROUTER_API_KEY")
if not _api_key:
    raise RuntimeError("OPENROUTER_API_KEY env var not set")
client = OpenAI(
    api_key=_api_key,
    base_url="https://openrouter.ai/api/v1",
    http_client=httpx.Client(proxy="http://agent.baidu.com:8891", timeout=300),
)

for label, include_adh in [("CONTROL_with_adh", True), ("ABLATION_no_adh", False)]:
    print(f"=== {label} ===")
    q = build_query(include_adh)
    resp = client.chat.completions.create(
        model="openai/gpt-4.1",
        max_completion_tokens=4000,
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": q},
        ],
        temperature=0,
    )
    text = resp.choices[0].message.content
    out = Path(f"results/ablation_{label}.md")
    out.write_text(text)
    n_new_h2 = sum(1 for line in text.split("\n") if "New H2" in line or "new H2" in line or "## " in line)
    print(f"  saved {out} ({len(text)} chars, ~{n_new_h2} H2-related lines)")
    print(f"  preview: {text[:300]}")
    print()
