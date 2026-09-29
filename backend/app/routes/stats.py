"""
app/routes/stats.py
────────────────────
GET /api/stats — aggregated complaint statistics.

Backed by a Redis read-through cache with 30-second TTL (per Requirements.xml §168).
Response includes X-Cache: HIT or MISS header so the frontend can display it.
Cache is explicitly invalidated whenever a new complaint is created or a status changes.
"""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.redis import get_redis
from app.repositories.complaint_repository import ComplaintRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Stats"])

STATS_CACHE_KEY = "civicpulse:stats:v1"
STATS_CACHE_TTL = 30  # seconds


@router.get(
    "/stats",
    summary="Aggregated complaint statistics",
    description=(
        "Returns counts by status, priority, and category plus average triage latency. "
        "Redis-cached for 30 s. Inspects X-Cache response header: HIT or MISS."
    ),
)
async def get_stats(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    """
    Read-through cache pattern:
      1. Attempt Redis GET of pre-computed stats blob.
      2. Cache HIT  → return JSON + X-Cache: HIT header.
      3. Cache MISS → query Postgres, SET result in Redis (TTL 30s), X-Cache: MISS.
    """
    redis = get_redis()

    # ── Cache read ────────────────────────────────────────────────────────
    try:
        cached = await redis.get(STATS_CACHE_KEY)
        if cached:
            return JSONResponse(
                content=json.loads(cached),
                headers={"X-Cache": "HIT"},
            )
    except Exception as exc:
        logger.warning("Stats cache read failed (%s); falling back to DB", exc)

    # ── Cache miss: query Postgres ────────────────────────────────────────
    repo = ComplaintRepository(session)
    stats = await repo.get_stats()

    # ── Populate cache ─────────────────────────────────────────────────────
    try:
        await redis.set(STATS_CACHE_KEY, json.dumps(stats), ex=STATS_CACHE_TTL)
    except Exception as exc:
        logger.warning("Stats cache write failed (%s); serving uncached", exc)

    return JSONResponse(
        content=stats,
        headers={"X-Cache": "MISS"},
    )


async def invalidate_stats_cache() -> None:
    """
    Explicitly invalidate the stats cache key.

    Call this after any write operation (new complaint, status update) so the
    next GET /api/stats reflects the change immediately.
    """
    try:
        redis = get_redis()
        await redis.delete(STATS_CACHE_KEY)
        logger.debug("Stats cache invalidated")
    except Exception as exc:
        logger.warning("Failed to invalidate stats cache: %s", exc)
