"""GET /cost-stats endpoint — the demo closer."""

from fastapi import APIRouter, Request

from app.config import get_settings
from app.schemas import CostStatsResponse, EndpointStats

router = APIRouter(tags=["observability"])

_AVG_EXPENSIVE_COST_FALLBACK = 0.0015


@router.get("/cost-stats", response_model=CostStatsResponse, summary="Cumulative cost savings")
async def get_cost_stats(request: Request) -> CostStatsResponse:
    """Return cumulative cost statistics and estimated savings.

    Returns:
        CostStatsResponse with savings percentage — the client-facing proof.
    """
    settings = get_settings()
    cache = request.app.state.cache
    stats = request.app.state.cost_stats
    cache_stats = cache.get_stats()

    total_requests = stats["total_requests"]
    cheap_calls = stats["cheap_calls"]
    expensive_calls = stats["expensive_calls"]
    total_cost = round(stats["cheap_cost_usd"] + stats["expensive_cost_usd"], 6)

    avg_expensive = (
        stats["expensive_cost_usd"] / expensive_calls
        if expensive_calls > 0
        else _AVG_EXPENSIVE_COST_FALLBACK
    )

    estimated_without_routing = round(total_requests * avg_expensive, 6)
    estimated_savings = round(estimated_without_routing - total_cost, 6)
    savings_pct = (
        round((estimated_savings / estimated_without_routing) * 100, 2)
        if estimated_without_routing > 0
        else 0.0
    )

    dashboard_url = (
        f"https://cloud.langfuse.com/project/{settings.langfuse_project_id}/traces"
        if settings.langfuse_project_id
        else "https://cloud.langfuse.com"
    )

    return CostStatsResponse(
        total_requests=total_requests,
        cache_hits=cache_stats["hits"],
        cache_hit_rate_pct=cache_stats["hit_rate_pct"],
        cheap_model_stats=EndpointStats(
            total_calls=cheap_calls,
            total_cost_usd=round(stats["cheap_cost_usd"], 6),
        ),
        expensive_model_stats=EndpointStats(
            total_calls=expensive_calls,
            total_cost_usd=round(stats["expensive_cost_usd"], 6),
        ),
        total_cost_usd=total_cost,
        estimated_cost_without_routing_usd=estimated_without_routing,
        estimated_savings_usd=estimated_savings,
        estimated_savings_pct=savings_pct,
        langfuse_dashboard_url=dashboard_url,
    )
