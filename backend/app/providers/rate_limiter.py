"""
app/providers/rate_limiter.py
─────────────────────────────
Distributed Redis rate limiter for FastAPI routes.

Protects POST /api/complaints from exhausting free-tier LLM quotas.
Keyed by client IP using a 60-second fixed window counter in Redis.
Returns HTTP 429 with a 'Retry-After' header when the limit is exceeded.
"""

import logging
import time

from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

RATE_LIMIT_PREFIX = "ratelimit:complaints:"


class DistributedRateLimiter:
    """
    Fixed-window distributed rate limiter backed by Redis.
    """

    def __init__(self, limit: int | None = None, window_seconds: int = 60) -> None:
        self.limit = limit or settings.rate_limit_per_minute
        self.window_seconds = window_seconds
        # In-memory fallback if Redis is unavailable
        self._memory_counts: dict[str, tuple[int, float]] = {}

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, inspecting X-Forwarded-For if behind a reverse proxy."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # First IP in the comma-separated list is the original client
            return forwarded_for.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    async def is_rate_limited(self, client_ip: str, limit: int | None = None) -> tuple[bool, int]:
        """
        Check and record an increment for the given client IP.

        Returns
        -------
        tuple[bool, int]
            (is_limited, retry_after_seconds)
        """
        max_allowed = limit or self.limit
        now = time.time()
        window_index = int(now // self.window_seconds)
        redis_key = f"{RATE_LIMIT_PREFIX}{client_ip}:{window_index}"

        # Seconds remaining until this window expires
        seconds_remaining = max(1, int(self.window_seconds - (now % self.window_seconds)))

        try:
            redis = get_redis()
            # Atomically increment and set TTL if new key
            pipe = redis.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, self.window_seconds + 5)
            results = await pipe.execute()

            current_count = results[0]
            if current_count > max_allowed:
                logger.warning(
                    "Rate limit exceeded for IP=%s (%d/%d requests)",
                    client_ip,
                    current_count,
                    max_allowed,
                )
                return True, seconds_remaining

            return False, 0

        except (RedisError, ConnectionError, OSError) as exc:
            logger.warning("Redis rate limiter unavailable (%s); using in-memory fallback", exc)
            # In-memory fallback
            count, expiry = self._memory_counts.get(client_ip, (0, now + self.window_seconds))
            if now > expiry:
                count = 0
                expiry = now + self.window_seconds

            count += 1
            self._memory_counts[client_ip] = (count, expiry)

            if count > max_allowed:
                retry_after = max(1, int(expiry - now))
                return True, retry_after

            return False, 0

    async def __call__(self, request: Request) -> None:
        """
        FastAPI dependency callable.
        Raises HTTP 429 with 'Retry-After' header if client IP exceeds quota.
        """
        client_ip = self._get_client_ip(request)
        is_limited, retry_after = await self.is_rate_limited(client_ip)

        if is_limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Rate limit exceeded. Too many complaints submitted from this IP. "
                    "Please try again later."
                ),
                headers={"Retry-After": str(retry_after)},
            )


# Global dependency instance for routes
rate_limiter = DistributedRateLimiter()
