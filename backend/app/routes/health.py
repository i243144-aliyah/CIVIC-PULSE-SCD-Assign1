"""
app/routes/health.py
─────────────────────
Lightweight health-check endpoints for load-balancer / k8s probes.

GET /health/live   → always 200 (process is up)
GET /health/ready  → 200 if DB is reachable, 503 otherwise
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", summary="Liveness probe")
async def liveness() -> dict:
    """Returns 200 immediately – confirms the process is running."""
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
async def readiness(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    """
    Confirms the application can reach the PostgreSQL database.
    Returns 503 if the DB is not reachable so the load balancer can
    drain traffic from this instance during DB downtime.
    """
    try:
        await session.execute(text("SELECT 1"))
        return JSONResponse(content={"status": "ready"})
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "detail": str(exc)},
        )
