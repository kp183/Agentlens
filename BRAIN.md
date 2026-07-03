# AgentLens — Project Brain

Last updated: 2026-07-03

## What this is
AgentLens is an open-source, real-time observability and tracing platform for AI agents. It allows developers to capture trace hierarchies, analyze nested tool calls, and monitor token costs in real-time with zero-overhead.

It is designed for developers building production-grade LLM applications and agents. The integration pitch: add one line of code (`import agentlens as al; al.init()`) and call `al.instrument_openai()` to get automatic, zero-config trace and span collection.

## Architecture
- Backend: FastAPI, SQLAlchemy (async), asyncpg, Alembic, Redis (cache/pubsub), PostgreSQL 16
- Frontend: Next.js 15, TypeScript, TailwindCSS, TanStack Query, Clerk (auth)
- SDK: Python, using non-blocking background queue thread, instrumentation via monkey-patching client libraries for OpenAI/Anthropic
- Repo layout:
  - `apps/api`: FastAPI ingestion and query backend
  - `apps/web`: Next.js developer dashboard
  - `packages/python-sdk`: Python SDK (`agentlens-py`)

## Distribution
- PyPI package name: agentlens-py (NOT "agentlens" — taken by an unrelated project; import statement stays `import agentlens as al`)
- Current published version: 0.1.1
- GitHub: kp183/Agentlens
- Live site: lens-neon.vercel.app

## History of major changes (chronological)
- PyPI naming collision found and fixed — agentlens -> agentlens-py
- CometAPI integration built and tested — fallback routing demo, cometapi_agentlens_demo.py
- glm-5.2 cost-tracking gap found (pricing.py only covered ~11 native OpenAI/Anthropic models) and fixed with verified CometAPI pricing
- Version bump 0.1.0 -> 0.1.1 after a stale build was caught missing the pricing fix
- 2026-07-03: Provider mislabeling fixed — OpenAI client wrapper now dynamically derives provider label from client base_url
- 2026-07-03: CometAPI pricing sync (`pricing_sync.py`) built, tested, and verified against `/api/models`
- 2026-07-03: Dedicated Tool Execution View added to web dashboard inspector for tool spans
- 2026-07-03: LangGraph auto-instrumentation (`langgraph.py`) built and tested with callback handler and graph execution hooks

## Known issues / design decisions and why
- Provider field in trace spans: Derived dynamically from the client's `base_url`. Defaults to `"openai"` for `api.openai.com` or unset base_url, returns `"cometapi"` for `cometapi.com` endpoints, and returns the raw hostname for custom gateways.
- Pricing table: Static dictionary in `pricing.py` enables fast, synchronous cost calculations without network latency in the client hot path. The `pricing_sync.py` script periodically fetches `/api/models` from CometAPI, converts per-million token pricing, and merges rates without overwriting entries with null pricing.
- Naming: "AgentLens" collides with 8+ unrelated GitHub projects (one with 100+ stars) — noted, not addressed, positioning concern only, not code.

## Community feedback log
- Debalina Chowdhury (LangChain community): LangGraph native instrumentation, trace diffing, first-class tool span visibility.
- Umar: offered to contribute; pointed at LangGraph instrumentation / Node.js SDK / Anthropic streaming edge cases.
- Justin: trust/autonomy metrics (override rate, rollback frequency, escalation quality) — open design conversation, not a queued build.
- CometAPI (Emery): integration partner; found and fixed provider-labeling and pricing gap bugs together; GET /api/models as pricing source.

## Roadmap status
| Item | Phase | Status | Commit | Notes |
|---|---|---|---|---|
| Provider mislabeling fix | 1 | done | 2c8bf8c | Derived from client base_url |
| CometAPI pricing sync | 2 | done | b91b83f | Fetches /api/models, skips null pricing |
| Tool span visibility | 2 | done | b91b83f | Dedicated Tool Details view in dashboard |
| LangGraph instrumentation | 3 | done | 6f27c0f | Callback handler and CompiledStateGraph monkey-patch |
| Trace diffing | 3 | not started | | |
