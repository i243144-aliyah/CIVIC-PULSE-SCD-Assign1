import os

import pytest

# Default to Redis DB 1 so your local DB 0 is not wiped; CI can supply its service URL.
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")

from app.core.redis import close_redis, get_redis


@pytest.fixture(autouse=True)
async def cleanup_redis_between_tests():
    # 1. Flush test Redis DB before test starts (fixes stale cache & fallback test)
    redis_client = get_redis()
    if hasattr(redis_client, "__await__"):
        redis_client = await redis_client

    await redis_client.flushdb()

    yield

    # 2. Close the global singleton socket before pytest destroys the event loop
    result = close_redis()
    if hasattr(result, "__await__"):
        await result
