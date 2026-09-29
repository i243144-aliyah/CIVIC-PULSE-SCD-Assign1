"""
app/core/redis.py
─────────────────
Async Redis client connection and healthcheck utilities.
"""

import logging

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """
    Get or create a singleton async Redis connection pool.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the global Redis client pool."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def check_redis_health() -> bool:
    """
    Verify Redis connectivity for readiness probe.
    Returns True if PING succeeds, False otherwise.
    """
    try:
        client = get_redis()
        res = await client.ping()
        return bool(res)
    except Exception as exc:
        logger.warning("Redis healthcheck failed: %s", exc)
        return False
