"""SearchQA evaluator — SQuAD-style Exact Match + token-level F1.

Mirrors the evaluator API of evaluators/wtq_compare.py and
evaluators/xlsx_compare.py so the rest of the pipeline can treat
SearchQA assessments uniformly.

The metric matches the MRQA-2019 / SQuAD official scorer:
  - ``normalize``: lowercase, strip articles ("a/an/the"), strip
    punctuation (using string.punctuation), collapse whitespace.
  - ``compute_em``: prediction matches a gold answer iff their normalized
    forms are byte-identical. Returns 1.0 if any of the gold answers
    matches; 0.0 otherwise.
  - ``compute_f1``: max over gold answers of token-overlap F1
    (precision = #common / #pred_tokens, recall = #common / #gold_tokens).

For the SkillGrad-shaped pipeline we expose ``compute_accuracy`` /
``format_comparison`` with the same shape as the WTQ evaluator. The
headline ``accuracy`` reported is **EM** (1.0 or 0.0 — matches Search-R1
/ R1-Searcher convention); F1 is included in the dict for diagnostics
and as a soft signal if any module wants continuous reward.

Public API used by the bench adapter::

    compute_accuracy(target_strings, predicted_strings)
        → {"accuracy", "match_count", "total_count", "f1", "em"}
    format_comparison(target_strings, predicted_strings)
        → str (human-readable for diagnoser context)
"""

from __future__ import annotations

import re
import string
from collections import Counter


_ARTICLE_RE = re.compile(r"\b(a|an|the)\b", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_TABLE = str.maketrans({c: " " for c in string.punctuation})


def _normalize(s: str) -> str:
    """SQuAD normalization: lower, strip articles/punct, collapse whitespace."""
    if not isinstance(s, str):
        s = str(s)
    s = s.lower()
    s = s.translate(_PUNCT_TABLE)
    s = _ARTICLE_RE.sub(" ", s)
    s = _WHITESPACE_RE.sub(" ", s).strip()
    return s


def _tokens(s: str) -> list[str]:
    return _normalize(s).split()


def compute_em(prediction: str, golds: list[str]) -> float:
    pn = _normalize(prediction)
    return 1.0 if any(pn == _normalize(g) for g in golds) else 0.0


def _f1_pair(prediction: str, gold: str) -> float:
    p_toks = _tokens(prediction)
    g_toks = _tokens(gold)
    if not p_toks or not g_toks:
        return float(p_toks == g_toks)
    common = Counter(p_toks) & Counter(g_toks)
    n = sum(common.values())
    if n == 0:
        return 0.0
    precision = n / len(p_toks)
    recall = n / len(g_toks)
    return 2 * precision * recall / (precision + recall)


def compute_f1(prediction: str, golds: list[str]) -> float:
    return max((_f1_pair(prediction, g) for g in golds), default=0.0)


def _first_predicted(predicted_strings: list[str]) -> str:
    """SearchQA expects a single short answer; if executor wrote multi-line,
    use the first non-empty line."""
    for line in predicted_strings:
        if line and line.strip():
            return line.strip()
    return ""


def compute_accuracy(
    target_strings: list[str], predicted_strings: list[str],
) -> dict:
    """SkillGrad-shaped accuracy dict.

    - ``accuracy`` = EM (0.0 / 1.0). Headline metric.
    - ``f1`` = token-overlap F1 over best gold (continuous, useful as
      soft signal).
    - ``match_count`` / ``total_count`` mirror the xlsx_compare shape:
      we report 1/1 on EM, 0/1 otherwise (SearchQA is single-answer).
    """
    pred = _first_predicted(predicted_strings)
    em = compute_em(pred, target_strings)
    f1 = compute_f1(pred, target_strings)
    return {
        "accuracy":    em,
        "match_count": int(em),
        "total_count": 1,
        "em":          em,
        "f1":          f1,
    }


def format_comparison(
    target_strings: list[str], predicted_strings: list[str],
) -> str:
    """Human-readable diff for the diagnoser context."""
    pred = _first_predicted(predicted_strings)
    em = compute_em(pred, target_strings)
    f1 = compute_f1(pred, target_strings)
    lines = [
        f"Question expected (any of {len(target_strings)}): {target_strings}",
        f"Predicted: {pred!r}",
        f"EM: {em:.0f}, F1: {f1:.3f}",
    ]
    if em == 0.0:
        lines.append(f"Normalized expected: {[_normalize(g) for g in target_strings]}")
        lines.append(f"Normalized predicted: {_normalize(pred)!r}")
    return "\n".join(lines)
