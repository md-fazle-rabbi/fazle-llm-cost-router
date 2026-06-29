"""Query complexity scorer — decides which LLM to route to."""

import re
from dataclasses import dataclass

import litellm

from app.config import get_settings


@dataclass
class ComplexityResult:
    """Structured result from the complexity scorer."""

    score: float
    token_count: int
    keyword_score: float
    is_complex: bool


_COMPLEX_PATTERNS: list[str] = [
    r"\banalyze\b", r"\banalyse\b", r"\bcompare\b", r"\bcontrast\b",
    r"\bevaluate\b", r"\bassess\b", r"\bcritique\b",
    r"\bwrite\b", r"\bcreate\b", r"\bgenerate\b", r"\bdraft\b",
    r"\bimplements?\b", r"\bdebug\b", r"\boptimize\b", r"\balgorithm\b",
    r"\bprove\b", r"\bderive\b", r"\barchitect\b", r"\bdesign\b",
    r"\bstrategy\b", r"\bplan\b", r"\breason\b",
]

_SIMPLE_PATTERNS: list[str] = [
    r"\bwhat is\b", r"\bwho is\b", r"\bwhen\b", r"\bwhere\b",
    r"\bdefine\b", r"\blist\b", r"\bname\b", r"\bhow many\b",
    r"\byes or no\b", r"\bis it\b",
]


def score_complexity(
    prompt: str,
    system_prompt: str | None = None,
) -> ComplexityResult:
    """Score prompt complexity to determine LLM routing decision.

    Args:
        prompt: The user query.
        system_prompt: Optional system context.

    Returns:
        ComplexityResult with score, token count, and routing decision.
    """
    settings = get_settings()
    full_text = prompt.lower()
    if system_prompt:
        full_text = f"{system_prompt.lower()} {full_text}"

    messages = [{"role": "user", "content": prompt}]
    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})

    try:
        token_count = litellm.token_counter(
            model="gpt-3.5-turbo",
            messages=messages,
        )
    except Exception:
        token_count = len(prompt.split())

    token_ratio = min(token_count / (settings.max_tokens_cheap * 3), 1.0)
    token_score = round(token_ratio * 0.3, 3)

    complex_hits = sum(
        1 for p in _COMPLEX_PATTERNS if re.search(p, full_text)
    )
    simple_hits = sum(
        1 for p in _SIMPLE_PATTERNS if re.search(p, full_text)
    )

    keyword_score = min(complex_hits * 0.2, 0.7) - min(simple_hits * 0.1, 0.3)
    keyword_score = round(max(0.0, keyword_score), 3)

    final_score = round(min(token_score + keyword_score, 1.0), 3)
    is_complex = final_score >= settings.complexity_threshold

    return ComplexityResult(
        score=final_score,
        token_count=token_count,
        keyword_score=keyword_score,
        is_complex=is_complex,
    )
