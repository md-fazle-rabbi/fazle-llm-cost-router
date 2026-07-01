"""Pydantic V2 request and response schemas — the API contract."""

from typing import Literal, cast
from pydantic import BaseModel, Field


class RouteRequest(BaseModel):
    """Incoming request to the /route endpoint."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        description="User query to route to the optimal LLM",
    )
    system_prompt: str | None = Field(
        default=None,
        max_length=5_000,
        description="Optional system prompt for the LLM",
    )
    force_model: Literal["cheap", "expensive"] | None = Field(
        default=None,
        description="Override routing — force cheap or expensive model",
    )


class RouteResponse(BaseModel):
    """Response from the /route endpoint."""

    answer: str
    model_used: str
    complexity_score: float
    routing_decision: Literal["cheap", "expensive"]
    cost_usd: float
    cache_hit: bool
    prompt_tokens: int
    completion_tokens: int


class EndpointStats(BaseModel):
    """Per-model cost statistics."""

    total_calls: int = 0
    total_cost_usd: float = 0.0


class CostStatsResponse(BaseModel):
    """Response from the /cost-stats endpoint — the demo closer."""

    total_requests: int
    cache_hits: int
    cache_hit_rate_pct: float
    cheap_model_stats: EndpointStats
    expensive_model_stats: EndpointStats
    total_cost_usd: float
    estimated_cost_without_routing_usd: float
    estimated_savings_usd: float
    estimated_savings_pct: float
    langfuse_dashboard_url: str


RoutingDecision = Literal["cheap", "expensive"]


def validate_routing_decision(value: str) -> RoutingDecision:
    if value not in ("cheap", "expensive"):
        raise ValueError(f"Invalid routing_decision in cache: {value!r}")
    return cast(RoutingDecision, value)
