"""FastAPI app factory — lifespan manages Redis pool + LiteLLM tracing."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis # type: ignore
from fastapi import FastAPI

from app.cache import CacheManager
from app.config import get_settings
from app.routers import llm, stats
from app.tracing import setup_tracing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: Redis pool + Langfuse tracing. Shutdown: clean disconnect."""
    settings = get_settings()

    # --- [STARTUP] ---
    redis_pool = aioredis.ConnectionPool.from_url(
        settings.redis_url,
        max_connections=20,
        decode_responses=False,
    )
    app.state.redis_pool = redis_pool
    app.state.cache = CacheManager(redis_pool)

    # In-memory cost counters
    app.state.cost_stats = {
        "total_requests": 0,
        "cheap_calls": 0,
        "expensive_calls": 0,
        "cheap_cost_usd": 0.0,
        "expensive_cost_usd": 0.0,
    }

    # LiteLLM → Langfuse callback setup
    setup_tracing()

    yield

    # --- [SHUTDOWN] ---
    await redis_pool.aclose()


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="fazle-llm-cost-router",
        description="Intelligent LLM cost routing with Redis caching and Langfuse observability.",
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.include_router(llm.router)
    app.include_router(stats.router)

    return app


app = create_app()
