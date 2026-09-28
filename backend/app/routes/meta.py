"""
app/routes/meta.py
──────────────────
Observability surface endpoints:
  - GET /api/meta/providers: Reports active triage provider and cache statistics.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.core.observability import metrics
from app.providers.cache import triage_cache
from app.providers.triage.factory import get_triage_provider

router = APIRouter(prefix="/meta", tags=["Metadata & Observability"])


@router.get("/providers", summary="Active triage provider and cache metrics")
async def get_providers_metadata():
    """
    Returns active triage provider configuration and triage cache hit-rate metrics.
    """
    active_provider = get_triage_provider()
    cache_stats = await triage_cache.get_stats()

    return {
        "active_provider": getattr(active_provider, "name", settings.triage_provider),
        "engine": getattr(active_provider, "engine", "none"),
        "configured_provider": settings.triage_provider,
        "recent_outcomes": metrics.recent_outcomes(),
        "cache": cache_stats,
    }
