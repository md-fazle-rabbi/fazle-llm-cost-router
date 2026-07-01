"""POST /route endpoint the core product."""

from fastapi import APIRouter, Request

from app.cost_router import route_and_complete
from app.schemas import RouteRequest, RouteResponse, validate_routing_decision
router = APIRouter(tags=["routing"])


@router.post("/route", response_model=RouteResponse, summary="Route query to optimal LLM")
async def route_query(payload: RouteRequest, request: Request) -> RouteResponse:
    """Route a query to the cheapest sufficient LLM, with caching.

    Args:
        payload: Validated request (prompt, system_prompt, force_model).
        request: FastAPI request object (for app.state access).

    Returns:
        RouteResponse with answer, model used, and exact cost.
    """
    cache = request.app.state.cache
    cost_stats = request.app.state.cost_stats

    # --- [Cache Check Lua atomic lock] ---
    cached_data, lock_acquired = await cache.get_with_retry(payload.prompt)

    if cached_data is not None:
        # CACHE HIT $0.00 cost, instant return
        cost_stats["total_requests"] += 1
        return RouteResponse(
            answer=cached_data["answer"],
            model_used=cached_data["model_used"],
            complexity_score=cached_data["complexity_score"],
            routing_decision=validate_routing_decision(cached_data["routing_decision"]),
            cost_usd=0.0,
            cache_hit=True,
            prompt_tokens=cached_data["prompt_tokens"],
            completion_tokens=cached_data["completion_tokens"],
        )

    # --- [Cache MISS call actual LLM] ---
    try:
        result = await route_and_complete(
            prompt=payload.prompt,
            system_prompt=payload.system_prompt,
            force_model=payload.force_model,
        )
    except Exception:
        await cache.release_lock(payload.prompt)
        raise

    # --- [Stats Update in-memory] ---
    cost_stats["total_requests"] += 1
    if result.routing_decision == "cheap":
        cost_stats["cheap_calls"] += 1
        cost_stats["cheap_cost_usd"] += result.cost_usd
    else:
        cost_stats["expensive_calls"] += 1
        cost_stats["expensive_cost_usd"] += result.cost_usd

    # --- [Store in Redis cache] ---
    await cache.store(
        payload.prompt,
        {
            "answer": result.answer,
            "model_used": result.model_used,
            "complexity_score": result.complexity_score,
            "routing_decision": result.routing_decision,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
        },
    )

    return RouteResponse(
        answer=result.answer,
        model_used=result.model_used,
        complexity_score=result.complexity_score,
        routing_decision=validate_routing_decision(result.routing_decision),
        cost_usd=result.cost_usd,
        cache_hit=False,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )

