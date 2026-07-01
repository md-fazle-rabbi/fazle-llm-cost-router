"""LiteLLM + Langfuse observability setup."""

import os
from app.config import get_settings


def setup_tracing() -> None:
    """Configure LiteLLM callbacks to send all traces to Langfuse.

    Called once at app startup inside lifespan.
    Graceful degradation: if Langfuse keys are missing, app still runs.

    Uses the OTEL-based Langfuse integration ("langfuse_otel"), not the
    legacy SDK-based callback ("langfuse"). The legacy callback imports
    langfuse's Python client internals directly and is still pinned to
    v2-era APIs on the LiteLLM side, so it breaks on langfuse v3/v4
    (AttributeError: module 'langfuse' has no attribute 'version').
    langfuse_otel instead exports spans straight to Langfuse's OTLP
    endpoint over HTTP Basic Auth, so it's unaffected by which langfuse
    package version is installed.
    """
    import litellm

    settings = get_settings()

    # OWASP LLM02:2025 — inject API keys from env, never hardcode
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key

    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

    if settings.langfuse_secret_key:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_OTEL_HOST"] = settings.langfuse_base_url

        litellm.callbacks = ["langfuse_otel"]

    # --- Network resilience (Windows / intermittent connectivity) ---
    # litellm defaults to aiohttp for async transport, which (a) doesn't
    # respect HTTP_PROXY/HTTPS_PROXY env vars like httpx does, and (b) has
    # shown intermittent SocketTimeoutError hangs on some Windows setups
    # reaching Google's Gemini/Vertex endpoints. Falling back to httpx and
    # forcing IPv4 avoids both classes of silent 30s timeouts.
    litellm.disable_aiohttp_transport = True
    litellm.force_ipv4 = True