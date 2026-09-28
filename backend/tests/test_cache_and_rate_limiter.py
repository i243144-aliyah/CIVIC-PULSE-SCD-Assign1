"""
Tests for Redis 24h content-hash triage caching and distributed rate limiting.
"""

import pytest
from fastapi import HTTPException, Request

from app.core.enums import ComplaintCategory, ComplaintPriority
from app.providers.cache import TriageCache, compute_content_hash
from app.providers.rate_limiter import DistributedRateLimiter
from app.schemas.triage import TriageResult


def test_content_hash_normalization():
    """Verify compute_content_hash normalizes casing and whitespace."""
    text1 = "Burst pipe flooding Street 12"
    loc1 = "Main Street"

    text2 = "  burst   pipe   flooding  street  12  "
    loc2 = "MAIN  STREET"

    hash1 = compute_content_hash(text1, loc1)
    hash2 = compute_content_hash(text2, loc2)

    assert hash1 == hash2


@pytest.mark.asyncio
async def test_triage_cache_hit_rate_measurement():
    """
    Verify 24h content-hash cache stores results and measures hit rate accurately:
    1st call -> MISS, 2nd call -> HIT.
    """
    cache = TriageCache()
    await cache.reset_stats()

    text = "Large open sinkhole in center lane of arterial road"
    loc = "Arterial Road North"

    # Initial check: Cache MISS
    res = await cache.get(text, loc)
    assert res is None

    # Populate cache
    expected = TriageResult(
        category=ComplaintCategory.roads,
        priority=ComplaintPriority.high,
        summary="Large open sinkhole in center lane",
        confidence=0.98,
    )
    await cache.set(text, loc, expected, ttl=86400)

    # Second check: Cache HIT
    hit_res = await cache.get(text, loc)
    assert hit_res is not None
    assert hit_res.category == ComplaintCategory.roads
    assert hit_res.priority == ComplaintPriority.high
    assert hit_res.summary == expected.summary

    # Verify hit rate metrics
    stats = await cache.get_stats()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1
    assert stats["total_requests"] >= 2
    assert 0.0 < stats["hit_rate"] <= 1.0
    assert "hit_rate_pct" in stats


@pytest.mark.asyncio
async def test_distributed_rate_limiter_exceeded():
    """
    Verify DistributedRateLimiter blocks requests exceeding quota with 429 and Retry-After.
    """
    limiter = DistributedRateLimiter(limit=3, window_seconds=60)
    test_ip = "192.168.1.100"

    # First 3 requests must be allowed
    for _ in range(3):
        limited, _ = await limiter.is_rate_limited(test_ip)
        assert not limited

    # 4th request must be rejected with retry_after
    limited, retry_after = await limiter.is_rate_limited(test_ip)
    assert limited is True
    assert 1 <= retry_after <= 60


@pytest.mark.asyncio
async def test_rate_limiter_fastapi_dependency_exception():
    """
    Verify rate limiter callable raises HTTP 429 with 'Retry-After' header.
    """
    limiter = DistributedRateLimiter(limit=1, window_seconds=60)

    # Mock request from a unique test IP
    scope = {
        "type": "http",
        "client": ("10.0.0.99", 54321),
        "headers": [],
    }
    req = Request(scope)

    # 1st request succeeds
    await limiter(req)

    # 2nd request must raise 429
    with pytest.raises(HTTPException) as exc_info:
        await limiter(req)

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) >= 1
