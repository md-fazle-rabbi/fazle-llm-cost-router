"""LiteLLM + Langfuse observability setup."""

import os
from app.config import get_settings


def setup_tracing() -> None:
    """Configure LiteLLM callbacks to send all traces to Langfuse.

    Called once at app startup inside lifespan.
    Graceful degradation: if Langfuse keys are missing, app still runs.
    """
    settings = get_settings()

    # OWASP LLM02:2025 — inject API keys from env, never hardcode
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key

    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

    if settings.langfuse_secret_key:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_HOST"] = settings.langfuse_base_url

        import litellm
        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]
