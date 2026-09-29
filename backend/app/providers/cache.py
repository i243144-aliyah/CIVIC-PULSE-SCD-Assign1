"""
app/providers/cache.py
──────────────────────
Redis-backed content-hash cache for complaint triage results.

Requirements:
  1. 24-hour TTL on cached triage results.
  2. Key derived from SHA-256 content hash of normalized location and complaint text.
  3. Metric counters for cache hits and misses.
  4. Reporting function for hit-rate observability.
"""

import hashlib
import logging
from typing import Any

from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis import get_redis
from app.schemas.triage import TriageResult

logger = logging.getLogger(__name__)

CACHE_PREFIX = "triage:cache:"
STATS_HITS_KEY = "triage:stats:hits"
STATS_MISSES_KEY = "triage:stats:misses"


def compute_content_hash(text: str, location: str) -> str:
    """
    Generate a deterministic SHA-256 hash for the given location and complaint text.
    Whitespace is normalized and text lowercased to maximize cache hit likelihood.
    """
    norm_text = " ".join(text.lower().split())
    norm_loc = " ".join(location.lower().split())
    payload = f"{norm_loc}::{norm_text}".encode()
    return hashlib.sha256(payload).hexdigest()


class TriageCache:
    """
    Manages 24-hour content-hash caching and hit-rate measurement for triage results.
    """

    def __init__(self, ttl: int | None = None) -> None:
        self.ttl = ttl or settings.triage_cache_ttl_seconds
        # In-memory fallback if Redis is unavailable
        self._memory_cache: dict[str, str] = {}
        self._memory_hits = 0
        self._memory_misses = 0

    async def get(self, text: str, location: str) -> TriageResult | None:
        """
        Look up a cached TriageResult by content hash.
        Updates hit/miss counters and returns TriageResult or None.
        """
        content_hash = compute_content_hash(text, location)
        key = f"{CACHE_PREFIX}{content_hash}"

        try:
            redis = get_redis()
            cached_json = await redis.get(key)
            if cached_json:
                await redis.incr(STATS_HITS_KEY)
                logger.info("TriageCache HIT for hash=%s", content_hash[:12])
                return TriageResult.model_validate_json(cached_json)

            await redis.incr(STATS_MISSES_KEY)
            logger.debug("TriageCache MISS for hash=%s", content_hash[:12])
            return None

        except (RedisError, ConnectionError, OSError) as exc:
            logger.warning("Redis triage cache unavailable (%s); using in-memory fallback", exc)
            if content_hash in self._memory_cache:
                self._memory_hits += 1
                return TriageResult.model_validate_json(self._memory_cache[content_hash])
            self._memory_misses += 1
            return None

    async def set(
        self,
        text: str,
        location: str,
        result: TriageResult,
        ttl: int | None = None,
    ) -> None:
        """
        Store a TriageResult in the cache with the configured TTL (default 24h).
        """
        content_hash = compute_content_hash(text, location)
        key = f"{CACHE_PREFIX}{content_hash}"
        data = result.model_dump_json()
        expire_time = ttl or self.ttl

        try:
            redis = get_redis()
            await redis.set(key, data, ex=expire_time)
            logger.debug("TriageCache SET for hash=%s (ttl=%ds)", content_hash[:12], expire_time)
        except (RedisError, ConnectionError, OSError) as exc:
            logger.warning("Failed to write to Redis triage cache (%s); storing in-memory", exc)
            self._memory_cache[content_hash] = data

    async def get_stats(self) -> dict[str, Any]:
        """
        Measure and report triage cache hits, misses, total, and hit rate percentage.
        """
        try:
            redis = get_redis()
            hits_str = await redis.get(STATS_HITS_KEY)
            misses_str = await redis.get(STATS_MISSES_KEY)

            hits = int(hits_str or 0)
            misses = int(misses_str or 0)
        except (RedisError, ConnectionError, OSError):
            hits = self._memory_hits
            misses = self._memory_misses

        total = hits + misses
        hit_rate = (hits / total) if total > 0 else 0.0

        return {
            "hits": hits,
            "misses": misses,
            "total_requests": total,
            "hit_rate": round(hit_rate, 4),
            "hit_rate_pct": f"{round(hit_rate * 100, 2)}%",
        }

    async def reset_stats(self) -> None:
        """Reset hit and miss counters (useful for test isolation)."""
        try:
            redis = get_redis()
            await redis.delete(STATS_HITS_KEY, STATS_MISSES_KEY)
        except Exception as exc:
            logger.debug("Could not reset Redis stats: %s", exc)
        self._memory_hits = 0
        self._memory_misses = 0


# Global singleton instance for easy import
triage_cache = TriageCache()
