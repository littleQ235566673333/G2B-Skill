"""Reorganize WTQ SKILL.md into mode-selector form by slicing original sections."""
from pathlib import Path

src_path = Path("results/runs/g2b-v8_gpt-5.4_wtq/train/final_skill/wtq/SKILL.md")
src = src_path.read_text()
lines = src.split("\n")

MODE_OF_SECTION = {
    "Inspect structure before choosing an operation": "Schema Grounding",
    "Count qualifying records": "Standard",
    "Follow next or previous valid entries": "Standard",
    "Derive a scalar from a composite cell": "Verification",
    "Collapse consecutive years into a span": "Verification",
    "Compute comparisons over entities, not table adjacency": "Plan-first",
    "Match repeated entities with explicit relation checks": "Plan-first",
}

# Common Pitfalls bullet (substring) -> mode
PITFALL_OF_MODE = {
    "Mapping a condition to the wrong similarly named column": "Schema Grounding",
    "Guessing generic labels, row scope": "Schema Grounding",
    "Returning an identifier, ordinal, code, or header": "Verification",
    "Returning a bare intermediate number": "Verification",
    "Returning a shortened head word": "Verification",
    "Returning separate year atoms": "Verification",
    "Returning a cell from one matched row when the question": "Verification",
    "Treating parenthetical day tags": "Schema Grounding",
    "Treating previous or next as a status-filtered search": "Standard",
    "Treating repeated-entity questions as raw set intersection": "Plan-first",
    "Returning raw cell text when the question asks for one numeric component": "Verification",
    "Treating informal comparative phrasing as row adjacency": "Plan-first",
    "Returning multiple candidates to a singular question": "Verification",
    "Returning serialized string text with backslashes": "Verification",
}

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

buckets = {"Schema Grounding": [], "Verification": [], "Plan-first": [], "Standard": []}
for title, (s, e) in sections.items():
    if title == "Common Pitfalls":
        continue
    mode = MODE_OF_SECTION[title]
    body_lines = lines[s : e + 1]
    if body_lines and body_lines[0].startswith("## "):
        body_lines[0] = "#" + body_lines[0]
    body = "\n".join(body_lines).rstrip()
    buckets[mode].append(body)

pitfalls_s, pitfalls_e = sections["Common Pitfalls"]
pitfall_lines = lines[pitfalls_s : pitfalls_e + 1]
pitfall_buckets = {"Schema Grounding": [], "Verification": [], "Plan-first": [], "Standard": []}
for pl in pitfall_lines:
    if not pl.strip().startswith("- "):
        continue
    matched = None
    for key, mode in PITFALL_OF_MODE.items():
        if key in pl:
            matched = mode
            break
    if matched is None:
        raise SystemExit(f"Unmatched pitfall: {pl.strip()[:80]}")
    pitfall_buckets[matched].append(pl)

for mode, items in pitfall_buckets.items():
    if items:
        block = "#### Common pitfalls (" + mode.lower() + ")\n\n" + "\n".join(items)
        buckets[mode].append(block)

TRIGGERS = {
    "Schema Grounding": "Column meaning, row scope, or table layout uncertain",
    "Verification": "Output shape: cardinality, denotation type, or composite parse",
    "Plan-first": "Comparison vs adjacency, or repeated-entity relation check",
    "Standard": "Direct count or sequence-step on a clear column",
}

selector_block = """## Execution Mode Selector

Before solving, identify the dominant risk and choose one mode:
- Schema Grounding Mode: """ + TRIGGERS["Schema Grounding"] + """
- Verification Mode: """ + TRIGGERS["Verification"] + """
- Plan-first Mode: """ + TRIGGERS["Plan-first"] + """
- Standard Mode: """ + TRIGGERS["Standard"]

parts = [preamble, "", selector_block, ""]
for mode in ["Schema Grounding", "Verification", "Plan-first", "Standard"]:
    parts.append(f"## Mode: {mode}")
    parts.append("")
    for block in buckets[mode]:
        parts.append(block)
        parts.append("")

output = "\n".join(parts).rstrip() + "\n"
out_path = Path("analysis/precheck_a/WTQ_mode_selector.md")
out_path.write_text(output)
print(f"Wrote: {out_path}")
print(f"Original lines: {len(lines)}, output lines: {len(output.split(chr(10)))}")

src_content_lines = set(l for l in lines if l.strip() and not l.startswith("## "))
out_lines = output.split("\n")
out_content_lines = set(
    l for l in out_lines
    if l.strip() and not l.startswith("## ") and not l.startswith("### ") and not l.startswith("#### ")
)
missing = src_content_lines - out_content_lines
if missing:
    print(f"!! MISSING ({len(missing)}):")
    for m in sorted(missing)[:10]:
        print(f"   {m[:100]}")
else:
    print("✓ All non-header source lines preserved verbatim")
