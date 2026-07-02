"""Redis async cache manager with Lua atomic locking."""

import asyncio
import hashlib
import json
from pathlib import Path

import redis.asyncio as aioredis  # type: ignore
from redis.exceptions import ConnectionError as RedisConnectionError  # type: ignore

from app.config import get_settings


# --- [Lua Script Loader] ---
_LUA_SCRIPT_PATH = Path(__file__).parent.parent / "lua" / "cache_lock.lua"
_LUA_SCRIPT: str = _LUA_SCRIPT_PATH.read_text(encoding="utf-8")

# Lock TTL — 30 seconds।
_LOCK_TTL_SECONDS: int = 30


class CacheManager:
    """Async Redis cache manager with atomic Lua locking."""

    def __init__(self, pool: aioredis.ConnectionPool) -> None:
        """Initialize with a shared Redis connection pool.

        Args:
            pool: Shared async Redis connection pool from lifespan.
        """
        # --- [Connection Pool] ---
        self._pool = pool

        # --- [In-Memory Counters] ---
        self._hits: int = 0
        self._misses: int = 0

    # --- [Cache Key Generator] ---
    def _make_cache_key(self, prompt: str) -> str:
        """Generate a safe Redis cache key from a prompt.

        Args:
            prompt: Raw user prompt.

        Returns:
            Hashed Redis key string.

        SHA256 hash = irreversible, collision-safe।
        """
        hash_val = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        return f"llm_cache:{hash_val}"

    def _make_lock_key(self, cache_key: str) -> str:
        """Generate the lock key for a given cache key.

        Args:
            cache_key: The base cache key.

        Returns:
            Lock key string.
        """
        return f"{cache_key}:lock"

    async def get_or_lock(
        self, prompt: str
    ) -> tuple[dict | None, bool]:
        """Atomically check cache or acquire a compute lock.

        Args:
            prompt: User prompt to look up.

        Returns:
            Tuple of (cached_data, lock_acquired).
            - (data, False)  = cache HIT — use data directly
            - (None, True)   = cache MISS + lock acquired — call LLM
            - (None, False)  = lock held by another — wait and retry
        """
        # --- [Redis Client] ---
        r = aioredis.Redis(connection_pool=self._pool)

        cache_key = self._make_cache_key(prompt)
        lock_key = self._make_lock_key(cache_key)

        try:
            # --- [Lua Atomic Execution] ---
            result = await r.eval(
                _LUA_SCRIPT,
                2,                          # numkeys = 2 (KEYS[1] and KEYS[2])
                cache_key,                  # KEYS[1]
                lock_key,                   # KEYS[2]
                str(_LOCK_TTL_SECONDS),     # ARGV[1]
            )

            # --- [Result Interpretation] ---

            if result in (b"LOCK_ACQUIRED", b"LOCK_WAIT"):
                # --- [Cache MISS] ---
                if result == b"LOCK_ACQUIRED":
                    self._misses += 1
                    return None, True
                return None, False

            # --- [Cache HIT] ---
            self._hits += 1
            return json.loads(result), False

        except RedisConnectionError:
            # --- [Graceful Degradation] ---
            # OWASP ASI05:2026 — fail-safe: never block user for infra issue।
            self._misses += 1
            return None, True

    async def get_with_retry(
        self,
        prompt: str,
        max_retries: int = 5,
    ) -> tuple[dict | None, bool]:
        """Retry getting from cache with exponential backoff.

        Args:
            prompt: User prompt.
            max_retries: Maximum retry attempts while waiting for lock.

        Returns:
            Same as get_or_lock() but retries LOCK_WAIT automatically.
        """
        for attempt in range(max_retries):
            cached_data, lock_acquired = await self.get_or_lock(prompt)

            if cached_data is not None or lock_acquired:
                return cached_data, lock_acquired

            # LOCK_WAIT: exponential backoff
            # attempt 0 → 0.1s, attempt 1 → 0.2s, attempt 2 → 0.4s
            wait_seconds = 0.1 * (2 ** attempt)
            await asyncio.sleep(wait_seconds)
        self._misses += 1
        return None, True

    async def store(self, prompt: str, data: dict) -> None:
        """Store LLM response in cache and release the compute lock.

        Args:
            prompt: The original user prompt.
            data: LLM response dict to cache.
        """
        settings = get_settings()
        r = aioredis.Redis(connection_pool=self._pool)

        cache_key = self._make_cache_key(prompt)
        lock_key = self._make_lock_key(cache_key)

        try:
            # --- [Atomic Pipeline] ---
            async with r.pipeline(transaction=True) as pipe:
                # setex = SET + EXPIRE
                # key, ttl_seconds, value
                pipe.setex(
                    cache_key,
                    settings.cache_ttl_seconds,
                    json.dumps(data),
                )
                pipe.delete(lock_key)
                await pipe.execute()

        except RedisConnectionError:
            pass

    async def release_lock(self, prompt: str) -> None:
        """Release the compute lock without storing a result.

        Called when LLM call fails — unlock so others can retry.

        Args:
            prompt: The prompt whose lock to release.
        """
        r = aioredis.Redis(connection_pool=self._pool)
        cache_key = self._make_cache_key(prompt)
        lock_key = self._make_lock_key(cache_key)
        try:
            await r.delete(lock_key)
        except RedisConnectionError:
            pass

    def get_stats(self) -> dict:
        """Return cache hit/miss statistics.

        Returns:
            Dict with hits, misses, total, and hit rate percentage.
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate_pct": round(hit_rate, 2),
        }
