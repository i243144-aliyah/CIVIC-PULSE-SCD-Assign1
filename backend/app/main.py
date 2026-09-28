"""
app/main.py
───────────
FastAPI application factory.

Startup sequence
────────────────
1. Build the FastAPI app with metadata from settings.
2. Register exception handlers.
3. Mount all routers (health, complaints, meta under /api and /api/v1).
4. Manage Redis and database lifecycle on startup/shutdown.

IMPORTANT: This module does NOT call Base.metadata.create_all() or any
equivalent. All schema changes go through Alembic migrations.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.redis import close_redis
from app.routes.complaints import router as complaints_router
from app.routes.health import router as health_router
from app.routes.meta import router as meta_router
from app.routes.stats import router as stats_router

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)


def create_app() -> FastAPI:
    """
    Application factory – instantiate and configure the FastAPI app.
    """
    app = FastAPI(
        title="CivicPulse API",
        description=(
            "AI-assisted civic complaint management system. "
            "Complaints are triaged automatically using LLMs, local Ollama, or deterministic rules."
        ),
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        debug=settings.app_debug,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handlers ─────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred. Please try again later."},
        )

    # ── Routers ───────────────────────────────────────────────────────────
    # Health endpoints: /health and /ready
    app.include_router(health_router)

    # Main API endpoints: mounted at /api (assignment contract) and /api/v1 (versioned)
    app.include_router(complaints_router, prefix="/api")
    app.include_router(complaints_router, prefix="/api/v1")

    # Metadata & Observability: /api/meta/providers
    app.include_router(meta_router, prefix="/api")
    app.include_router(meta_router, prefix="/api/v1")

    # Stats: GET /api/stats (30s Redis read-through cache, X-Cache header)
    app.include_router(stats_router, prefix="/api")
    app.include_router(stats_router, prefix="/api/v1")

    # ── Lifecycle events ──────────────────────────────────────────────────
    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info(
            "CivicPulse API starting | env=%s triage_provider=%s debug=%s",
            settings.app_env,
            settings.triage_provider,
            settings.app_debug,
        )

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("CivicPulse API shutting down - closing Redis pools.")
        await close_redis()

    return app


# Module-level app instance consumed by uvicorn / ASGI servers.
app = create_app()
