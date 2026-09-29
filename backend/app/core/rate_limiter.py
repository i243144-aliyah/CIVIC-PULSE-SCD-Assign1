from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError

from app.core.redis import get_redis

RATE_LIMIT_REQUESTS = 10  # Max requests
RATE_LIMIT_WINDOW = 60  # Time window in seconds


async def check_rate_limit(request: Request) -> None:
    """
    Fixed-window rate limiter by client IP.
    Returns HTTP 429 with Retry-After header if limit exceeded.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    key = f"rate_limit:{client_ip}"

    try:
        redis_client = get_redis()
        current_requests = await redis_client.incr(key)
        if current_requests == 1:
            await redis_client.expire(key, RATE_LIMIT_WINDOW)

        if current_requests > RATE_LIMIT_REQUESTS:
            ttl = await redis_client.ttl(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(max(ttl, 1))},
            )
    except RedisError:
        pass  # Fail open if Redis is temporarily unreachable
