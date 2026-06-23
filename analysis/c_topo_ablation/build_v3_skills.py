"""Build 5 skill variants for v3 ablation.

Pa (= Sa = v2 baseline): end + bare imperative — already exists as v2_skill_v8_plus_neg
Pb: middle + bare — v8 base + 5 rules inserted before "## Common Pitfalls"
Pc: top + bare — v8 base + "## Critical Avoidances (read first)" right after frontmatter
Sb: end + Why-anchored — v8 base + 5 rules each with "Why:" sentence
Sc: end + process-style — v8 base + 5 rules recast as positive process steps

5 selected rules (matching v3 case selection):
  R1 oqa-112 (ratio direction)
  R2 oqa-14 (revised data)
  R5 oqa-118 (multi-step enumeration)
  R6 oqa-35 (reporting structure)
  R8 oqa-130 (currency conversion)
"""
from pathlib import Path
import shutil

V8_SKILL = Path("results/runs/g2b-v8_gpt-5.4_oqa-gpt54-smoke/train/final_skill/officeqa/SKILL.md")
V3_ROOT = Path("analysis/c_topo_ablation/v3_skills")

# Rule sets (only the 5 selected cases)
RULES_BARE = """- **R1 (aggregate, oqa-112):** When computing means of yearly ratios, compute each year's ratio first, THEN average — do not aggregate sums of A and B first and divide. The ratio "A to B" means A/B; reversing yields the reciprocal.
- **R2 (comparison, oqa-14):** When the question requests "revised" or "post-war updated" figures for a WWII-era period (1934-1946), DO NOT use contemporaneous bulletins (1942 for 1942 data). Revisions appear in LATER bulletins (1947+); use the most recent bulletin in the source set for both years.
- **R5 (growth_rate, oqa-118):** For multi-step calculations involving multiple separate data sources (regression coefficients + external GDP + counterfactual), enumerate each required input as a found/missing checklist BEFORE coding any step. List required_value, source_document, value_quoted, basis_unit. Do not use memory-supplied values for external statistics.
- **R6 (lookup, oqa-35):** When the question specifies a particular reporting structure (e.g., "Air Force expenditures still charged to Army appropriations"), use ONLY the bulletin source where that structure holds. Pre-1947 unified, post-1947 may separate. State which bulletin's reporting structure is being used BEFORE extracting Army values.
- **R8 (comparison, oqa-130):** When the question asks for a value in a target currency (CAD, EUR, etc.) using a specific reference period exchange rate, ALWAYS apply the conversion explicitly: state the exchange rate and the source bulletin row. Do NOT report values in source currency (USD) without conversion. Exchange rate must come from the bulletin's explicit currency table for that reference period.
"""

# Why-anchored variant (generalized causal framing, no real case_id)
RULES_WHY = """- **R1 (aggregate, oqa-112):** When computing means of yearly ratios, compute each year's ratio first, THEN average — do not aggregate sums of A and B first and divide. The ratio "A to B" means A/B; reversing yields the reciprocal. **Why:** aggregating before averaging produces a weighted mean that depends on the magnitude of A and B, not the per-period ratios; in financial questions this systematically inflates or deflates the result.
- **R2 (comparison, oqa-14):** When the question requests "revised" or "post-war updated" figures for a WWII-era period (1934-1946), DO NOT use contemporaneous bulletins. Revisions appear in LATER bulletins (1947+). **Why:** wartime bulletins reported preliminary unrevised figures; the official Treasury revisions for PWA/housing exclusions appear only in 1947+ post-war reconciliation tables. Using the contemporaneous source returns the unrevised number.
- **R5 (growth_rate, oqa-118):** For multi-step calculations with multiple separate data sources, enumerate each required input as a found/missing checklist BEFORE coding any step. **Why:** multi-step questions are dominated by missing-input errors more than by computation errors; LLM-default behavior is to hallucinate plausible values for unsourced inputs (especially external statistics like GDP), which cascades through downstream regression/ratio steps and produces large multiplicative errors.
- **R6 (lookup, oqa-35):** When the question specifies a particular reporting structure (e.g., "Air Force expenditures still charged to Army appropriations"), use ONLY the bulletin source where that structure holds. **Why:** the reporting structure for Army/Air Force changed in 1947 with the National Security Act; pre-1947 bulletins use unified Army-includes-AF structure, post-1947 may separate. Using the wrong-era bulletin returns the wrong sub-aggregate.
- **R8 (comparison, oqa-130):** When the question asks for a value in a target currency (CAD/EUR/etc.) using a specific reference period exchange rate, ALWAYS apply the conversion explicitly. **Why:** unit-conversion errors are the dominant failure mode in cross-currency comparison questions; LLM-default is to compute in the source currency (USD) and report without converting, producing the right number in the wrong unit.
"""

# Process-style variant (recast as v8's "Strategy that works well" voice)
RULES_PROCESS = """- **R1 (aggregate, oqa-112):** Before computing a ratio statistic over multiple periods, restate the numerator and denominator from the question in words. Compute each period's ratio independently, then aggregate. State the formula in pseudocode (e.g., `mean([receipts_y / defense_y for y in years])`) before executing.
- **R2 (comparison, oqa-14):** Before extracting a WWII-era value, check whether the question requests "revised", "updated", or "post-war reconciliation" figures. If yes, scan source bulletins by date and prefer the LATEST bulletin in the source set; the contemporaneous bulletin (1942 for 1942 data) gives unrevised numbers.
- **R5 (growth_rate, oqa-118):** For any multi-step calculation involving multiple data sources, write a found/missing input checklist before coding. List each required input with: (required_value, source_document, value_quoted, basis_unit). Block computation if any required input is "missing" or memory-supplied.
- **R6 (lookup, oqa-35):** Before extracting Army or Defense expenditure values, identify the reporting structure period explicitly. Pre-1947 bulletins use unified Army-includes-AF structure; post-1947 may separate. State which bulletin's reporting structure is being applied, and use that single bulletin's values consistently.
- **R8 (comparison, oqa-130):** Before reporting a value in a non-USD currency, write down the exchange rate source row and the conversion direction. The final answer must be in the requested currency unit; if the source bulletin's value is in USD, multiply by the explicit exchange-rate cell value before reporting.
"""

NEG_HEADER = "\n\n## Negative function rules (failure-mode-specific avoidance)\n\nThese rules describe specific failure patterns observed in convergent v8 failures. Apply them when the question pattern matches.\n\n"
PROCESS_HEADER = "\n\n## Function Rules (failure-mode-specific process steps)\n\nThese are process-step rules for known failure-mode patterns. Apply when the question pattern matches.\n\n"
TOP_HEADER = "## Critical Avoidances (read first)\n\nThese rules describe specific failure patterns observed in convergent failures. Apply them whenever the question pattern matches; they take precedence over general strategies below.\n\n"


def main():
    V3_ROOT.mkdir(parents=True, exist_ok=True)
    base_text = V8_SKILL.read_text(encoding="utf-8")

    # ── Pa = Sa = v2 baseline (already built; copy for completeness)
    pa_dir = V3_ROOT / "Pa" / "officeqa"; pa_dir.mkdir(parents=True, exist_ok=True)
    (pa_dir / "SKILL.md").write_text(
        base_text + NEG_HEADER + RULES_BARE, encoding="utf-8"
    )
    print(f"Pa: {pa_dir/'SKILL.md'} ({sum(1 for _ in (pa_dir/'SKILL.md').open())} lines)")

    # ── Pb: middle insertion (before "## Common Pitfalls")
    common_pitfalls_marker = "## Common Pitfalls"
    pb_text = base_text.replace(
        common_pitfalls_marker,
        PROCESS_HEADER.lstrip("\n") + RULES_BARE + "\n" + common_pitfalls_marker,
        1,
    )
    pb_dir = V3_ROOT / "Pb" / "officeqa"; pb_dir.mkdir(parents=True, exist_ok=True)
    (pb_dir / "SKILL.md").write_text(pb_text, encoding="utf-8")
    print(f"Pb: {pb_dir/'SKILL.md'} ({sum(1 for _ in (pb_dir/'SKILL.md').open())} lines)")

    # ── Pc: top insertion (after frontmatter `---...---\n`)
    parts = base_text.split("---\n", 2)
    if len(parts) >= 3:
        # parts = ['', frontmatter_yaml, rest]
        pc_text = "---\n" + parts[1] + "---\n\n" + TOP_HEADER + RULES_BARE + "\n" + parts[2].lstrip("\n")
    else:
        pc_text = TOP_HEADER + RULES_BARE + "\n" + base_text
    pc_dir = V3_ROOT / "Pc" / "officeqa"; pc_dir.mkdir(parents=True, exist_ok=True)
    (pc_dir / "SKILL.md").write_text(pc_text, encoding="utf-8")
    print(f"Pc: {pc_dir/'SKILL.md'} ({sum(1 for _ in (pc_dir/'SKILL.md').open())} lines)")

    # ── Sb: end + Why-anchored
    sb_dir = V3_ROOT / "Sb" / "officeqa"; sb_dir.mkdir(parents=True, exist_ok=True)
    (sb_dir / "SKILL.md").write_text(
        base_text + NEG_HEADER + RULES_WHY, encoding="utf-8"
    )
    print(f"Sb: {sb_dir/'SKILL.md'} ({sum(1 for _ in (sb_dir/'SKILL.md').open())} lines)")

    # ── Sc: end + process-style
    sc_dir = V3_ROOT / "Sc" / "officeqa"; sc_dir.mkdir(parents=True, exist_ok=True)
    (sc_dir / "SKILL.md").write_text(
        base_text + NEG_HEADER + RULES_PROCESS, encoding="utf-8"
    )
    print(f"Sc: {sc_dir/'SKILL.md'} ({sum(1 for _ in (sc_dir/'SKILL.md').open())} lines)")

    # ── Sanity check
    print("\nFirst 3 H2 sections per variant:")
    import re
    for vname in ["Pa", "Pb", "Pc", "Sb", "Sc"]:
        f = V3_ROOT / vname / "officeqa" / "SKILL.md"
        h2s = re.findall(r"^## .+$", f.read_text(encoding="utf-8"), flags=re.M)
        print(f"  {vname}: {h2s[:4]}...")


if __name__ == "__main__":
    main()
