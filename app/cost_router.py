"""LiteLLM-based cost router — decides model, calls LLM, returns cost."""

from dataclasses import dataclass

import litellm

from app.complexity_scorer import score_complexity
from app.config import get_settings


@dataclass
class RoutingResult:
    """Final routing decision + LLM response + exact cost."""

    answer: str
    model_used: str
    routing_decision: str
    complexity_score: float
    cost_usd: float
    prompt_tokens: int
    completion_tokens: int


async def route_and_complete(
    prompt: str,
    system_prompt: str | None = None,
    force_model: str | None = None,
) -> RoutingResult:
    """Score complexity, pick a model, call LiteLLM, return cost.

    Args:
        prompt: User query.
        system_prompt: Optional system context.
        force_model: "cheap" | "expensive" | None (override).

    Returns:
        RoutingResult with answer, model, cost breakdown.
    """
    settings = get_settings()

    complexity = score_complexity(prompt, system_prompt)

    if force_model == "cheap":
        routing_decision = "cheap"
    elif force_model == "expensive":
        routing_decision = "expensive"
    else:
        routing_decision = "expensive" if complexity.is_complex else "cheap"

    model = (
        settings.expensive_model
        if routing_decision == "expensive"
        else settings.cheap_model
    )

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = await litellm.acompletion(
        model=model,
        messages=messages,
        max_tokens=1024,
        timeout=30,
        metadata={
            "routing_decision": routing_decision,
            "complexity_score": complexity.score,
        },
    )

    if not isinstance(response, litellm.ModelResponse):
        raise TypeError(
            f"Expected ModelResponse, got {type(response).__name__} — streaming not supported here"
        )

    answer = response.choices[0].message.content or ""

    usage = getattr(response, "usage", None)
    if usage is not None:
        prompt_tokens = usage.prompt_tokens
        completion_tokens = usage.completion_tokens
    else:
        prompt_tokens = 0
        completion_tokens = 0

    cost_usd = litellm.completion_cost(completion_response=response)

    return RoutingResult(
        answer=answer,
        model_used=model,
        routing_decision=routing_decision,
        complexity_score=complexity.score,
        cost_usd=round(cost_usd, 6),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
