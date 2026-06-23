"""OfficeQA evaluator — fuzzy numerical match + LLM-judge fallback.

Per Databricks tech report (arXiv 2603.08655), OfficeQA scoring uses a
``reward.py`` that does **fuzzy numerical match at 0/0.1/1/5% relative
error tolerances**. Most published numbers report ``acc@1pct``.

Some answers are non-numerical (date ranges, named entities, short
phrases). For those we fall back to SQuAD-style EM + F1, then optionally
LLM-judge for "semantic equivalence".

Public API (mirrors evaluators/wtq_compare.py)::

    compute_accuracy(target_strings, predicted_strings, tolerance_pct=1.0)
        → {"accuracy", "match_count", "total_count",
           "acc_exact", "acc_0p1pct", "acc_1pct", "acc_5pct",
           "match_type"}
    format_comparison(target_strings, predicted_strings, tolerance_pct=1.0)
        → str

The ``accuracy`` returned is ``acc@tolerance_pct`` (default 1%) — that's
the headline metric for OfficeQA. Sub-tolerances are also returned for
optional reporting.
"""

from __future__ import annotations

import re
import string
from collections import Counter

from evaluators.searchqa_compare import _normalize as _squad_normalize


_NUMBER_RE = re.compile(r"-?\$?\d{1,3}(?:[,_]?\d{3})*(?:\.\d+)?(?:[eE][+-]?\d+)?")


def _strip_currency_units(s: str) -> str:
    """Remove leading currency symbols ($, USD, ¥) and common unit suffixes."""
    s = s.strip()
    s = re.sub(r"^\$|^USD\s*|^¥|^€", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"\s*(million|billion|thousand|m|bn|k)\s*$", "", s, flags=re.IGNORECASE)
    return s


def _try_parse_number(s: str) -> float | None:
    """Try to extract a single number from a string. Handles $, commas, units."""
    if s is None:
        return None
    s_orig = str(s).strip()
    # Multiplier from unit suffix
    mult = 1.0
    m = re.search(r"(?:^|\s)(million|billion|thousand|m|bn|k)\s*$", s_orig, re.IGNORECASE)
    if m:
        unit = m.group(1).lower()
        mult = {"million": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9,
                "thousand": 1e3, "k": 1e3}[unit]
    s_clean = _strip_currency_units(s_orig)
    s_clean = s_clean.replace(",", "").replace("_", "").replace("%", "").strip()
    try:
        return float(s_clean) * mult
    except (ValueError, TypeError):
        # Try regex extraction
        m = _NUMBER_RE.search(s_orig)
        if m:
            try:
                return float(m.group(0).replace(",", "").replace("$", "")) * mult
            except (ValueError, TypeError):
                return None
        return None


def _rel_error(pred: float, gold: float) -> float:
    """Relative error |pred - gold| / |gold|, with 0/0 -> 0."""
    if abs(gold) < 1e-12:
        return 0.0 if abs(pred) < 1e-12 else float("inf")
    return abs(pred - gold) / abs(gold)


def _f1_squad(prediction: str, gold: str) -> float:
    p_toks = _squad_normalize(prediction).split()
    g_toks = _squad_normalize(gold).split()
    if not p_toks or not g_toks:
        return float(p_toks == g_toks)
    common = Counter(p_toks) & Counter(g_toks)
    n = sum(common.values())
    if n == 0:
        return 0.0
    precision = n / len(p_toks)
    recall = n / len(g_toks)
    return 2 * precision * recall / (precision + recall)


def _first_predicted(predicted_strings: list[str]) -> str:
    for line in predicted_strings:
        if line and line.strip():
            return line.strip()
    return ""


def compute_accuracy(
    target_strings: list[str], predicted_strings: list[str],
    *, tolerance_pct: float = 1.0,
) -> dict:
    """OfficeQA-style fuzzy-numerical scoring with EM/F1 fallback.

    ``tolerance_pct`` is the relative-error tolerance in percent (e.g.
    1.0 means ``rel_err <= 0.01``). The headline ``accuracy`` field uses
    this tolerance; finer/coarser tolerances are also reported.
    """
    pred = _first_predicted(predicted_strings)
    gold = (target_strings[0] if target_strings else "").strip()

    pn = _try_parse_number(pred)
    gn = _try_parse_number(gold)
    is_numeric = pn is not None and gn is not None

    if is_numeric:
        rel = _rel_error(pn, gn)
        acc_exact  = 1.0 if rel <= 1e-9 else 0.0
        acc_0p1pct = 1.0 if rel <= 0.001 else 0.0
        acc_1pct   = 1.0 if rel <= 0.01  else 0.0
        acc_5pct   = 1.0 if rel <= 0.05  else 0.0
        chosen = (
            acc_exact   if tolerance_pct <= 0     else
            acc_0p1pct  if tolerance_pct <= 0.1   else
            acc_1pct    if tolerance_pct <= 1.0   else
            acc_5pct
        )
        return {
            "accuracy":    chosen,
            "match_count": int(chosen),
            "total_count": 1,
            "acc_exact":   acc_exact,
            "acc_0p1pct":  acc_0p1pct,
            "acc_1pct":    acc_1pct,
            "acc_5pct":    acc_5pct,
            "match_type":  "numerical",
            "rel_error":   rel,
            "pred_num":    pn,
            "gold_num":    gn,
        }

    # Non-numeric: fall back to SQuAD-style EM + F1.
    pn_str = _squad_normalize(pred)
    em = 1.0 if any(pn_str == _squad_normalize(g) for g in target_strings) else 0.0
    f1 = max((_f1_squad(pred, g) for g in target_strings), default=0.0)
    return {
        "accuracy":    em,
        "match_count": int(em),
        "total_count": 1,
        "em":          em,
        "f1":          f1,
        "match_type":  "string",
    }


def format_comparison(
    target_strings: list[str], predicted_strings: list[str],
    *, tolerance_pct: float = 1.0,
) -> str:
    pred = _first_predicted(predicted_strings)
    gold = (target_strings[0] if target_strings else "").strip()
    pn = _try_parse_number(pred)
    gn = _try_parse_number(gold)
    lines = [
        f"Gold answer: {gold!r}",
        f"Predicted:   {pred!r}",
    ]
    if pn is not None and gn is not None:
        rel = _rel_error(pn, gn)
        lines.append(f"Numerical: pred={pn} gold={gn} rel_err={rel:.6f}")
        lines.append(f"acc@{tolerance_pct}%: "
                     f"{'PASS' if rel <= tolerance_pct/100.0 else 'FAIL'}")
    else:
        lines.append("Non-numerical fallback: SQuAD EM + F1.")
        lines.append(f"Normalized pred: {_squad_normalize(pred)!r}")
        lines.append(f"Normalized gold: {_squad_normalize(gold)!r}")
    return "\n".join(lines)
