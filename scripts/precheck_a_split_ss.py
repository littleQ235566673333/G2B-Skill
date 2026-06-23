"""Reorganize SS SKILL.md into mode-selector form."""
from pathlib import Path

src_path = Path("results/runs/g2b-v8_gpt-5.4/train/final_skill/xlsx/SKILL.md")
src = src_path.read_text()
lines = src.split("\n")

# Section -> mode assignment (canonical 124-line train/final_skill version)
MODE_OF_SECTION = {
    "Classify the deliverable before writing": "Plan-first",
    "Edit cells and formulas from nearby sheet context": "Schema Grounding",
    "Simulate stateful traversal on an example": "Plan-first",
    "Process segmented ranges with block-aware sorting": "Schema Grounding",
    "Verify exact written output": "Verification",
    "FIFO ending inventory valuation": "Standard",
}

# Common Pitfalls bullet (substring) -> mode (only pitfalls present in canonical 124-line file)
PITFALL_OF_MODE = {
    "Skipping layout inspection": "Schema Grounding",
    "Mixing output modalities": "Plan-first",
    "Leaving traversal semantics implicit": "Plan-first",
    "Losing headers during block operations": "Schema Grounding",
    "Stopping at an intermediate artifact": "Verification",
    "Trusting a plausible formula string": "Verification",
    "Collapsing true zeros into blank display markers": "Verification",
    "Reversing FIFO layer direction": "Standard",
    "`data_only=True` destroys formulas on save": "Schema Grounding",
    "`ws.max_row` overcounts": "Schema Grounding",
}

# Slice sections
sections = {}
current_title = None
current_start = None
preamble_end = -1
for i, line in enumerate(lines):
    if line.startswith("## "):
        if current_title is not None:
            sections[current_title] = (current_start, i - 1)
        else:
            preamble_end = i - 1
        current_title = line[3:].strip()
        current_start = i
if current_title is not None:
    sections[current_title] = (current_start, len(lines) - 1)

preamble = "\n".join(lines[: preamble_end + 1]).rstrip()

# Bucket sections by mode
buckets = {"Schema Grounding": [], "Verification": [], "Plan-first": [], "Standard": []}
for title, (s, e) in sections.items():
    if title == "Common Pitfalls":
        continue
    mode = MODE_OF_SECTION[title]
    body_lines = lines[s : e + 1]
    # Demote section H2 to H3 to nest under Mode H2 (level-only edit, not text edit)
    if body_lines and body_lines[0].startswith("## "):
        body_lines[0] = "#" + body_lines[0]  # ## → ###
    body = "\n".join(body_lines).rstrip()
    buckets[mode].append(body)

# Common Pitfalls: distribute bullets
pitfalls_s, pitfalls_e = sections["Common Pitfalls"]
pitfall_lines = lines[pitfalls_s : pitfalls_e + 1]
# First two lines: "## Common Pitfalls\n\n"; bullets follow
pitfall_buckets = {"Schema Grounding": [], "Verification": [], "Plan-first": [], "Standard": []}
for pl in pitfall_lines:
    pl_stripped = pl.strip()
    if not pl_stripped.startswith("- **") and not pl_stripped.startswith("- `"):
        continue
    matched = None
    for key, mode in PITFALL_OF_MODE.items():
        if key in pl:
            matched = mode
            break
    if matched is None:
        raise SystemExit(f"Unmatched pitfall: {pl_stripped[:80]}")
    pitfall_buckets[matched].append(pl)

# Append pitfalls to each mode bucket as a sub-block
for mode, items in pitfall_buckets.items():
    if items:
        block = "#### Common pitfalls (" + mode.lower() + ")\n\n" + "\n".join(items)
        buckets[mode].append(block)

# Trigger sentences (≤15 token each)
TRIGGERS = {
    "Schema Grounding": "Workbook layout, headers, sheet structure unclear or composite",
    "Verification": "Output format, modality, exact value, or answer-shape risk",
    "Plan-first": "Multi-step decomposition, deliverable choice, or stateful traversal",
    "Standard": "Specific procedure: ordinal navigation or FIFO inventory",
}

selector_block = """## Execution Mode Selector

Before solving, identify the dominant risk and choose one mode:
- Schema Grounding Mode: """ + TRIGGERS["Schema Grounding"] + """
- Verification Mode: """ + TRIGGERS["Verification"] + """
- Plan-first Mode: """ + TRIGGERS["Plan-first"] + """
- Standard Mode: """ + TRIGGERS["Standard"]

# Assemble final output
parts = [preamble, "", selector_block, ""]
for mode in ["Schema Grounding", "Verification", "Plan-first", "Standard"]:
    parts.append(f"## Mode: {mode}")
    parts.append("")
    for block in buckets[mode]:
        parts.append(block)
        parts.append("")

output = "\n".join(parts).rstrip() + "\n"

out_path = Path("analysis/precheck_a/SS_mode_selector.md")
out_path.write_text(output)
print(f"Wrote: {out_path}")
print(f"Original lines: {len(lines)}")
print(f"Output lines:   {len(output.split(chr(10)))}")

# Validate verbatim preservation: every non-mode-header line in source should appear in output
src_content_lines = set(l for l in lines if l.strip() and not l.startswith("## "))
out_lines = output.split("\n")
out_content_lines = set(
    l for l in out_lines
    if l.strip()
    and not l.startswith("## ")
    and not l.startswith("### ")
    and not l.startswith("#### ")
)
missing = src_content_lines - out_content_lines
if missing:
    print(f"!! MISSING from output ({len(missing)} lines):")
    for m in sorted(missing)[:10]:
        print(f"   {m[:100]}")
else:
    print("✓ All non-header source lines preserved verbatim in output")
