"""WikiTableQuestions evaluator (Python 3 port of Stanford official ``evaluator.py``).

Original: ``evaluator.py`` in the Pasupat & Liang 2015 release (v1.0.2).
This port preserves the official denotation-equality scoring semantics:

  - normalize: diacritics, smart quotes/dashes, citations, parens, outer
    quotes, trailing period, whitespace, lowercase
  - Value types: String / Number / Date with their own equality rules
  - check_denotation: set-equality on (size, item-matching)

Differences from upstream
-------------------------
- Python 3 syntax (``str`` instead of ``unicode``/``basestring``,
  raw-string literals, ``print(...)`` calls, ``ABC`` metaclass).
- We do NOT use CoreNLP-tagged values. Stanford's tagged-data pipeline
  passes pre-canonicalized ``targetCanon`` strings alongside originals;
  we only have ``targetValue`` from the raw TSV. Practical impact: a
  small number of dates/numbers that CoreNLP would have canonicalized
  may be scored slightly stricter here. For our use this is fine — the
  acceptance gate is the SkillGrad pipeline, not a leaderboard.
- Adds ``compute_accuracy`` and ``format_comparison`` helpers shaped
  like ``evaluators.xlsx_compare`` so the rest of the pipeline can
  treat WTQ assessments uniformly.

Public API used by the bench adapter::

    from evaluators.wtq_compare import (
        compute_accuracy,    # → {"accuracy", "match_count", "total_count"}
        format_comparison,   # → str (human-readable diff)
        check_denotation,    # → bool (the strict official metric)
        to_value_list,       # str list → Value list (for callers)
    )
"""

from __future__ import annotations

import re
import unicodedata
from abc import ABC, abstractmethod
from math import isinf, isnan


# ─── String normalization ───────────────────────────────────────────────

def normalize(x: str) -> str:
    """Stanford WTQ string normalization. Idempotent under repeat application."""
    if not isinstance(x, str):
        x = str(x)
    # Remove diacritics
    x = "".join(
        c for c in unicodedata.normalize("NFKD", x)
        if unicodedata.category(c) != "Mn"
    )
    # Normalize quotes and dashes
    x = re.sub(r"[‘’´`]", "'", x)
    x = re.sub(r"[“”]", '"', x)
    x = re.sub(r"[‐‑‒–—−]", "-", x)
    while True:
        old_x = x
        # Remove citations ([...] / trailing markers)
        x = re.sub(r"((?<!^)\[[^\]]*\]|\[\d+\]|[•♦†‡*#+])*$", "", x.strip())
        # Remove details in parenthesis
        x = re.sub(r"(?<!^)( \([^)]*\))*$", "", x.strip())
        # Remove outermost quotation marks
        x = re.sub(r'^"([^"]*)"$', r"\1", x.strip())
        if x == old_x:
            break
    if x and x[-1] == ".":
        x = x[:-1]
    x = re.sub(r"\s+", " ", x).lower().strip()
    return x


# ─── Value types ────────────────────────────────────────────────────────

class Value(ABC):
    _normalized: str = ""

    @abstractmethod
    def match(self, other: "Value") -> bool: ...

    @property
    def normalized(self) -> str:
        return self._normalized


class StringValue(Value):
    def __init__(self, content: str):
        self._normalized = normalize(content)
        self._hash = hash(self._normalized)

    def __eq__(self, other):
        return isinstance(other, StringValue) and self.normalized == other.normalized

    def __hash__(self):
        return self._hash

    def __str__(self):
        return f"S{[self.normalized]}"

    __repr__ = __str__

    def match(self, other: Value) -> bool:
        return self.normalized == other.normalized


class NumberValue(Value):
    def __init__(self, amount: float, original_string: str | None = None):
        if abs(amount - round(amount)) < 1e-6:
            self._amount: float = int(amount)
        else:
            self._amount = float(amount)
        self._normalized = (
            normalize(original_string) if original_string else str(self._amount)
        )
        self._hash = hash(self._amount)

    @property
    def amount(self) -> float:
        return self._amount

    def __eq__(self, other):
        return isinstance(other, NumberValue) and self.amount == other.amount

    def __hash__(self):
        return self._hash

    def __str__(self):
        return f"N({self.amount}){[self.normalized]}"

    __repr__ = __str__

    def match(self, other: Value) -> bool:
        if self.normalized == other.normalized:
            return True
        if isinstance(other, NumberValue):
            return abs(self.amount - other.amount) < 1e-6
        return False

    @staticmethod
    def parse(text: str):
        try:
            return int(text)
        except (ValueError, TypeError):
            try:
                amount = float(text)
                if isnan(amount) or isinf(amount):
                    return None
                return amount
            except (ValueError, TypeError):
                return None


class DateValue(Value):
    def __init__(self, year: int, month: int, day: int, original_string: str | None = None):
        assert month == -1 or 1 <= month <= 12
        assert day == -1 or 1 <= day <= 31
        assert not (year == month == day == -1)
        self._year, self._month, self._day = year, month, day
        if original_string:
            self._normalized = normalize(original_string)
        else:
            self._normalized = "{}-{}-{}".format(
                year if year != -1 else "xx",
                month if month != -1 else "xx",
                day if day != -1 else "xx",
            )
        self._hash = hash((year, month, day))

    @property
    def ymd(self):
        return (self._year, self._month, self._day)

    def __eq__(self, other):
        return isinstance(other, DateValue) and self.ymd == other.ymd

    def __hash__(self):
        return self._hash

    def __str__(self):
        return f"D({self._year},{self._month},{self._day}){[self._normalized]}"

    __repr__ = __str__

    def match(self, other: Value) -> bool:
        if self.normalized == other.normalized:
            return True
        if isinstance(other, DateValue):
            return self.ymd == other.ymd
        return False

    @staticmethod
    def parse(text: str):
        try:
            ymd = text.lower().split("-")
            if len(ymd) != 3:
                return None
            year = -1 if ymd[0] in ("xx", "xxxx") else int(ymd[0])
            month = -1 if ymd[1] == "xx" else int(ymd[1])
            day = -1 if ymd[2] == "xx" else int(ymd[2])
            if year == month == day == -1:
                return None
            if month != -1 and not 1 <= month <= 12:
                return None
            if day != -1 and not 1 <= day <= 31:
                return None
            return (year, month, day)
        except (ValueError, AttributeError):
            return None


# ─── Conversion ─────────────────────────────────────────────────────────

def to_value(original_string: str, corenlp_value: str | None = None) -> Value:
    if isinstance(original_string, Value):
        return original_string
    src = corenlp_value if corenlp_value else original_string
    amount = NumberValue.parse(src)
    if amount is not None:
        return NumberValue(amount, original_string)
    ymd = DateValue.parse(src)
    if ymd is not None:
        if ymd[1] == ymd[2] == -1:
            return NumberValue(ymd[0], original_string)
        return DateValue(ymd[0], ymd[1], ymd[2], original_string)
    return StringValue(original_string)


def to_value_list(
    original_strings, corenlp_values=None,
) -> list[Value]:
    if corenlp_values is not None:
        assert len(original_strings) == len(corenlp_values)
        return list({to_value(x, y) for x, y in zip(original_strings, corenlp_values)})
    return list({to_value(x) for x in original_strings})


# ─── Denotation check (the official metric) ─────────────────────────────

def check_denotation(
    target_values: list[Value], predicted_values: list[Value],
) -> bool:
    if len(target_values) != len(predicted_values):
        return False
    for t in target_values:
        if not any(t.match(p) for p in predicted_values):
            return False
    return True


# ─── SkillGrad-shaped helpers (mirror evaluators/xlsx_compare API) ──────

def compute_accuracy(
    target_strings: list[str], predicted_strings: list[str],
) -> dict:
    """Return ``{"accuracy", "match_count", "total_count"}`` like xlsx_compare.

    - ``accuracy = 1.0`` iff strict denotation match (size + item matching).
    - On non-strict, fall back to a soft Jaccard-like score:
      ``match_count / max(len(target), len(predicted))``.
      Useful as continuous reward signal for group-relative advantage.
    """
    target = to_value_list(target_strings)
    predicted = to_value_list(predicted_strings)

    # Strict (official)
    if check_denotation(target, predicted):
        return {
            "accuracy": 1.0,
            "match_count": len(target),
            "total_count": len(target),
        }

    # Soft fallback
    matched = sum(1 for t in target if any(t.match(p) for p in predicted))
    denom = max(len(target), len(predicted), 1)
    return {
        "accuracy": matched / denom,
        "match_count": matched,
        "total_count": denom,
    }


def format_comparison(
    target_strings: list[str], predicted_strings: list[str],
) -> str:
    """Human-readable diff for the diagnoser. Mirrors xlsx_compare format."""
    target = to_value_list(target_strings)
    predicted = to_value_list(predicted_strings)
    is_correct = check_denotation(target, predicted)

    lines = [
        f"Expected ({len(target)}): {[str(v) for v in target]}",
        f"Predicted ({len(predicted)}): {[str(v) for v in predicted]}",
        f"Strict denotation match: {is_correct}",
        "",
    ]
    if not is_correct:
        unmatched = [
            str(t) for t in target if not any(t.match(p) for p in predicted)
        ]
        extra = [
            str(p) for p in predicted if not any(t.match(p) for t in target)
        ]
        if unmatched:
            lines.append(f"Unmatched targets: {unmatched}")
        if extra:
            lines.append(f"Extra predictions: {extra}")
    return "\n".join(lines)
