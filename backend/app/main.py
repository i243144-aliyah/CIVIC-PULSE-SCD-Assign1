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

import contextvars
import json
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine
from app.core.observability import metrics
from app.core.redis import close_redis
from app.routes.complaints import router as complaints_router
from app.routes.health import router as health_router
from app.routes.meta import router as meta_router
from app.routes.metrics import router as metrics_router
from app.routes.stats import router as stats_router

logger = logging.getLogger(__name__)
request_id_context: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JSONLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        for field in ("complaint_id", "provider", "error_class"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


logging.basicConfig(
    level=settings.log_level.upper(),
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
for handler in logging.getLogger().handlers:
    handler.setFormatter(JSONLogFormatter())


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "CivicPulse API starting | env=%s triage_provider=%s debug=%s",
        settings.app_env,
        settings.triage_provider,
        settings.app_debug,
    )
    try:
        yield
    finally:
        logger.info("CivicPulse API shutting down; closing connection pools.")
        try:
            await close_redis()
        finally:
            await engine.dispose()


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
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Cache"],
    )

    @app.middleware("http")
    async def request_observability(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", "")[:128] or str(uuid.uuid4())
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            metrics.observe_request(request.method, status_code, time.perf_counter() - started)
            request_id_context.reset(token)

    # ── Global exception handlers ─────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred. Please try again later."},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": [
                    {
                        "field": ".".join(str(part) for part in error["loc"]),
                        "message": error["msg"],
                        "type": error["type"],
                    }
                    for error in exc.errors()
                ]
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────
    # Health endpoints: /health and /ready
    app.include_router(health_router)
    app.include_router(metrics_router)

    # Main API endpoints: mounted at /api (assignment contract) and /api/v1 (versioned)
    app.include_router(complaints_router, prefix="/api")
    app.include_router(complaints_router, prefix="/api/v1")

    # Metadata & Observability: /api/meta/providers
    app.include_router(meta_router, prefix="/api")
    app.include_router(meta_router, prefix="/api/v1")

    # Stats: GET /api/stats (30s Redis read-through cache, X-Cache header)
    app.include_router(stats_router, prefix="/api")
    app.include_router(stats_router, prefix="/api/v1")

    return app


# Module-level app instance consumed by uvicorn / ASGI servers.
app = create_app()
