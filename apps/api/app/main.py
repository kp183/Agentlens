"""AgentLens API — application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.exceptions import AgentLensError, RateLimitError
from app.middleware.logging import RequestIDMiddleware, setup_logging

setup_logging()
from app.routers.api_keys import router as api_keys_router
from app.routers.health import router as health_router
from app.routers.ingest import router as ingest_router
from app.routers.orgs import router as orgs_router
from app.routers.traces import router as traces_router
from app.routers.ws import router as ws_router

logger = logging.getLogger(__name__)
settings = get_settings()

if settings.local_mode:
    import logging
    logging.getLogger("agentlens").warning(
        "⚠️  LOCAL_MODE is ENABLED — ALL authentication is BYPASSED. "
        "DO NOT run this configuration in production."
    )

app = FastAPI(
    title="AgentLens API",
    version=settings.api_version,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
)

# ── Middleware ────────────────────────────────────────────────────────────────

@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 5 * 1024 * 1024:
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": "Request body must not exceed 5MB",
                    "request_id": getattr(request.state, "request_id", "unknown"),
                }
            },
        )
    return await call_next(request)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
    return response

app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],  # explicit, not ["*"]
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# ── Exception handlers ────────────────────────────────────────────────────────


@app.exception_handler(AgentLensError)
async def agentlens_error_handler(request: Request, exc: AgentLensError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error("AgentLensError: %s", exc.message, extra={"request_id": request_id})
    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "request_id": request_id,
            }
        },
    )
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins_list:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    # Add Retry-After header for rate limit errors
    if isinstance(exc, RateLimitError):
        retry_after = getattr(exc, "retry_after", 60)
        response.headers["Retry-After"] = str(retry_after)
    return response


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("Unhandled exception", extra={"request_id": request_id})
    response = JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "request_id": request_id,
            }
        },
    )
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins_list:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


# ── Startup ───────────────────────────────────────────────────────────────────


@app.on_event("startup")
async def run_migrations() -> None:
    """Run Alembic migrations on startup in development mode."""
    if settings.environment != "development":
        return

    import asyncio
    from alembic import command
    from alembic.config import Config

    logger.info("Running Alembic migrations (environment=development)...")
    try:
        alembic_cfg = Config("alembic.ini")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, command.upgrade, alembic_cfg, "head")
        logger.info("Alembic migrations complete.")
    except Exception as exc:
        logger.error("Migration failed: %s", exc)
        raise


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health_router)
app.include_router(orgs_router)
app.include_router(api_keys_router)
app.include_router(ingest_router)
app.include_router(traces_router)
app.include_router(ws_router)
