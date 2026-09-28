"""
app/main.py
───────────
FastAPI application factory.

Startup sequence
────────────────
1. Build the FastAPI app with metadata from settings.
2. Register exception handlers (validation errors → 422, catch-all → 500).
3. Mount all routers.
4. Verify DB connectivity on startup (readiness log, NOT schema creation).

IMPORTANT: This module does NOT call Base.metadata.create_all() or any
equivalent.  All schema changes go through Alembic migrations.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routes.complaints import router as complaints_router
from app.routes.health import router as health_router

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)


def create_app() -> FastAPI:
    """
    Application factory – instantiate and configure the FastAPI app.

    Using a factory instead of a module-level app object makes the app
    testable: tests can call create_app() with different settings.
    """
    app = FastAPI(
        title="CivicPulse API",
        description=(
            "AI-assisted civic complaint management system. "
            "Complaints are triaged automatically using LLMs or deterministic rules."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        debug=settings.app_debug,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    # Adjust `allow_origins` per environment in production.
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
    app.include_router(health_router)
    app.include_router(complaints_router, prefix="/api/v1")

    # ── Startup event ─────────────────────────────────────────────────────
    @app.on_event("startup")
    async def on_startup() -> None:
        """
        Log startup.  Does NOT create tables – that is Alembic's job.
        A deliberate DB ping is done via GET /health/ready by the orchestrator.
        """
        logger.info(
            "CivicPulse API starting | env=%s debug=%s",
            settings.app_env,
            settings.app_debug,
        )

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("CivicPulse API shutting down.")

    return app


# Module-level app instance consumed by uvicorn / ASGI servers.
app = create_app()
