"""LiveMathBench evaluator — LLM-judge for math-answer equivalence.

Math answers are heterogeneous formulas: ``8√5 - 16``, ``(2n+2)/3``,
``\\boxed{(0, 1/2)}``, ``x = -1 \\pm \\sqrt{3}``. Pure exact-match
under-scores by 5-15pp because models emit equivalent forms with
different surface syntax. The OpenCompass paper uses a Qwen2.5-72B
judge with ~95% agreement vs GPT-4o judge.

We use **the proxy GPT-4.1** as judge by default (cheaper than
GPT-5.4, more consistent than rule-based matching). The judge is
prompted to return `EQUIVALENT` or `NOT_EQUIVALENT` only — easy to
parse, low variance.

Public API (mirrors evaluators/wtq_compare.py)::

    compute_accuracy(target_strings, predicted_strings)
        → {"accuracy", "match_count", "total_count", "judge_verdict",
           "judge_reasoning"}
    format_comparison(target_strings, predicted_strings)
        → str

Notes
-----
- ``compute_accuracy`` is **synchronous** to keep the bench protocol
  signature unchanged. Internally it spawns an asyncio call to the LLM
  judge and waits on it. Concurrency is bounded by run_execute's existing
  semaphore — judges are NOT batched here.
- Falls back to a normalized exact-match if the judge call fails (e.g.,
  network), so downstream training does not crash on transient errors.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Optional

from openai import OpenAI


# ─── Surface normalization (exact-match fallback) ───────────────────────

_BOXED_RE = re.compile(r"\\boxed\{([^{}]+)\}")
_WS_RE = re.compile(r"\s+")
_LATEX_TRIVIAL = [
    (r"\\left", ""), (r"\\right", ""),
    (r"\\!", ""), (r"\\,", ""), (r"\\;", ""), (r"\\:", ""), (r"\\ ", " "),
    (r"\\dfrac", r"\\frac"), (r"\\tfrac", r"\\frac"),
]


def _strip_boxed(s: str) -> str:
    m = _BOXED_RE.search(s)
    if m:
        return m.group(1).strip()
    return s.strip()


def _normalize(s: str) -> str:
    s = _strip_boxed(str(s))
    for pat, rep in _LATEX_TRIVIAL:
        s = re.sub(pat, rep, s)
    s = _WS_RE.sub(" ", s).strip().lower()
    return s


def _exact_match(prediction: str, golds: list[str]) -> bool:
    pn = _normalize(prediction)
    return any(pn == _normalize(g) for g in golds if g)


def _first_predicted(predicted_strings: list[str]) -> str:
    """Take the first non-empty line; if the executor wrote multi-line, the
    last \\boxed{} usually wins — try that path too."""
    if not predicted_strings:
        return ""
    raw = "\n".join(predicted_strings)
    boxed = _BOXED_RE.findall(raw)
    if boxed:
        return boxed[-1].strip()
    for line in predicted_strings:
        if line and line.strip():
            return line.strip()
    return ""


# ─── LLM judge ──────────────────────────────────────────────────────────

JUDGE_PROMPT = """You are evaluating whether a candidate math answer is mathematically equivalent to the gold answer.

Question:
{question}

Gold answer:
{gold}

Candidate answer:
{prediction}

Two answers are EQUIVALENT if they denote the same mathematical object after normalizing trivial surface differences (LaTeX vs ASCII, with/without \\boxed{{}}, ordering of set/tuple elements, equivalent fractions like 1/2 vs 0.5, equivalent roots like sqrt(2) vs 2^(1/2), simplification like 4/2 vs 2). They are NOT EQUIVALENT if they denote different values or different mathematical objects (e.g. answering only one solution when multiple are required, or wrong sign).

Respond with EXACTLY one of these two tokens on the first line:
EQUIVALENT
NOT_EQUIVALENT

You MAY add a brief justification on subsequent lines."""


def _make_judge_client() -> OpenAI:
    """Build an OpenAI client pointed at the configured proxy/endpoint.

    Reads OPENAI_API_KEY + OPENAI_BASE_URL from environment (same as the
    rest of the project).
    """
    base_url = os.environ.get("OPENAI_BASE_URL")
    api_key = os.environ.get("OPENAI_API_KEY")
    return OpenAI(base_url=base_url, api_key=api_key)


def _judge_sync(
    question: str, gold: str, prediction: str,
    model: str = "gpt-4.1", timeout: float = 60.0,
) -> tuple[bool, str]:
    """Call the judge model synchronously. Returns (is_equivalent, raw_text).

    On any failure, returns (False, "<judge-error: ...>") — the caller
    should fall back to exact-match.
    """
    client = _make_judge_client()
    prompt = JUDGE_PROMPT.format(
        question=question[:4000],
        gold=gold[:1000],
        prediction=prediction[:1000],
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200,
            timeout=timeout,
        )
        text = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return False, f"<judge-error: {e}>"

    first = text.splitlines()[0].strip().upper() if text else ""
    if first.startswith("EQUIVALENT"):
        return True, text
    return False, text


# ─── Public API (SkillGrad-shaped) ──────────────────────────────────────

def compute_accuracy(
    target_strings: list[str], predicted_strings: list[str],
    *, question: str = "", judge_model: str = "gpt-4.1",
) -> dict:
    """Score one prediction against gold via LLM-judge.

    ``question`` is bench-side context — the bench adapter passes it
    through ``assess()``. Without it, the judge still runs but its
    decision quality drops slightly (no problem context to disambiguate
    "is this answer relevant").
    """
    pred = _first_predicted(predicted_strings)
    gold = (target_strings[0] if target_strings else "").strip()

    # Fast path: surface-form exact match → no judge call needed.
    if pred and gold and _exact_match(pred, target_strings):
        return {
            "accuracy":    1.0,
            "match_count": 1,
            "total_count": 1,
            "judge_verdict": "EXACT_MATCH",
            "judge_reasoning": "",
        }

    # Empty prediction never matches.
    if not pred:
        return {
            "accuracy":    0.0,
            "match_count": 0,
            "total_count": 1,
            "judge_verdict": "EMPTY_PREDICTION",
            "judge_reasoning": "",
        }

    is_eq, reasoning = _judge_sync(question, gold, pred, model=judge_model)
    return {
        "accuracy":    1.0 if is_eq else 0.0,
        "match_count": 1 if is_eq else 0,
        "total_count": 1,
        "judge_verdict": "EQUIVALENT" if is_eq else "NOT_EQUIVALENT",
        "judge_reasoning": reasoning[:500],
    }


def format_comparison(
    target_strings: list[str], predicted_strings: list[str],
    *, question: str = "",
) -> str:
    """Human-readable diff for the diagnoser context."""
    pred = _first_predicted(predicted_strings)
    gold = (target_strings[0] if target_strings else "").strip()
    return (
        f"Gold answer: {gold!r}\n"
        f"Predicted:   {pred!r}\n"
        f"Surface exact-match: {_exact_match(pred, target_strings)}\n"
        f"(Judge verdict computed in compute_accuracy if not exact.)"
    )
