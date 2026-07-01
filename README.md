# fazle-llm-cost-router

> Intelligent LLM cost routing — complexity-based model selection, Redis caching with atomic Lua locking, and Langfuse cost observability.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-009688?style=flat)](https://fastapi.tiangolo.com)
[![LiteLLM](https://img.shields.io/badge/LiteLLM-Multi--Provider-7C3AED?style=flat)](https://litellm.ai)
[![Redis](https://img.shields.io/badge/Redis-Lua%20Atomic-DC382D?style=flat)](https://redis.io)
[![Langfuse](https://img.shields.io/badge/Langfuse-v4%20Cost%20Tracking-FF6B35?style=flat)](https://langfuse.com)

## Live Demo

| Endpoint | URL |
|---|---|
| Swagger UI | `https://fazle-llm-cost-router.onrender.com/docs` |
| Route Query | `POST /route` |
| Cost Stats | `GET /cost-stats` |

## The Problem This Solves

Most teams send every query to their most expensive model. This router:
1. Scores query complexity (token count + semantic keywords)
2. Routes simple queries to a cheap model, complex queries to a capable one
3. Caches identical queries in Redis — zero cost on repeats
4. Uses a Lua script for atomic cache locking — prevents duplicate LLM calls under concurrent load
5. Logs every routing decision and cost to Langfuse

## Results

- Simple query (`gemini-3.1-flash-lite`): $0.25 / 1M input tokens | $1.50 / 1M output tokens
- Complex query (`gemini-3.5-flash`): $1.50 / 1M input tokens | $9.00 / 1M output tokens
- Cached repeat query: $0.00
- Typical savings on mixed traffic: **30-70%** vs always-expensive routing

## Architecture

Client → /route → Redis (Lua atomic check) → cache HIT? return
↓ MISS
complexity_scorer → cheap/expensive model
↓
LiteLLM → Gemini/Claude → Langfuse trace
↓
Redis store (atomic) → response

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.116+ |
| LLM Gateway | LiteLLM (100+ providers, unified cost tracking) |
| Cache | Redis (redis.asyncio) + Lua atomic scripts |
| Observability | Langfuse v4 |
| Package Manager | uv |
| Deploy | Render (Docker) |

## Free-Tier Constraints (Transparency)

| Resource | Free Limit |
|---|---|
| Upstash Redis | 500K commands/month, 256MB data, 10GB bandwidth/month |
| Render Web Service | 750 instance-hours/month, 5GB bandwidth/month, 15-min spin-down (cold start ~30-60s) |

> This demo runs on free infrastructure to show the pattern works end-to-end. Production client deployments move to Upstash Pay-as-you-go ($0.20/100K commands) or Render Starter ($7/mo, no spin-down) — both trivial cost increases relative to LLM API savings this router delivers.

## Local Setup

```bash
git clone https://github.com/md-fazle-rabbi/fazle-llm-cost-router
cd fazle-llm-cost-router
cp .env.example .env
# Fill in GEMINI_API_KEY, REDIS_URL, LANGFUSE keys

docker run -d -p 6379:6379 redis:7-alpine  # local Redis
uv sync
uv run uvicorn app.main:app --reload
```

## Security

- OWASP LLM01:2025 — Prompt length capped at 10,000 chars
- OWASP LLM02:2025 — Cache keys are SHA256 hashed (no raw PII in Redis)
- OWASP LLM09:2025 — Complex queries routed to stronger models (hallucination mitigation)
- OWASP ASI02:2026 — Atomic Lua locking prevents duplicate expensive calls (tool misuse via race condition)

## Author

**Md. Fazle Rabbi** — AI Engineer · FastAPI · LangGraph · MCP · OWASP LLM:2025
