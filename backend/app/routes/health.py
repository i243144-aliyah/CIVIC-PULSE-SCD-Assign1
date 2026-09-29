"""
app/routes/health.py
────────────────────
Health probes strictly distinguished for Kubernetes and container readiness:

GET /health  (Liveness)   → 200 if process is up. MUST NOT touch the database.
GET /ready   (Readiness)  → 200 only if Postgres AND Redis are both reachable.
                           Returns 503 naming the failed dependency.
"""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.database import check_database_health
from app.core.redis import check_redis_health

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness probe")
@router.get("/health/live", summary="Liveness probe (legacy alias)")
async def liveness() -> dict:
    """
    Liveness probe.
    Must NOT touch the database or Redis. Failing this restarts the container.
    """
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
@router.get("/health/ready", summary="Readiness probe (legacy alias)")
async def readiness() -> JSONResponse:
    """
    Readiness probe.
    Returns 200 only if Postgres and Redis are both reachable.
    Returns 503 naming the failed dependency so traffic is drained.
    """
    postgres_ok = await check_database_health()
    redis_ok = await check_redis_health()

    if postgres_ok and redis_ok:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready", "database": "connected", "redis": "connected"},
        )

    failed = []
    if not postgres_ok:
        failed.append("database")
    if not redis_ok:
        failed.append("redis")

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "not_ready",
            "failed_dependencies": failed,
            "detail": f"Dependency check failed: {', '.join(failed)} unreachable",
        },
    )
