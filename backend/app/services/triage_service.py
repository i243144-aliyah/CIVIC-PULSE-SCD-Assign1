"""
app/services/triage_service.py
───────────────────────────────
Triage orchestration service — the core intelligence and lifecycle manager.

Layer contract
──────────────
• Receives validated Pydantic schemas from the routes layer.
• Owns business logic: caching, provider selection, fallback handling, state machine.
• Delegates ALL database persistence to ComplaintRepository.
• Returns ORM instances (or raises domain exceptions) to the routes layer.

AI Triage Flow (Phase 2)
────────────────────────
1. Check Redis content-hash cache (24h TTL) to avoid duplicate inference.
2. If cache miss, invoke active TriageProvider (LLM, Ollama, Rules, Simulated).
3. If LLM fails (timeout/429/5xx after retry), fallback to RuleBasedTriage (rules:fallback).
4. Cache result in Redis for duplicate complaints.
5. Persist complaint with triage metadata (category, priority, summary, latency).
"""

import asyncio
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ComplaintCategory, ComplaintStatus, TriagedBy
from app.core.observability import metrics
from app.providers.cache import triage_cache
from app.providers.triage.base import TriageProvider, TriageResult
from app.providers.triage.factory import get_triage_provider
from app.providers.triage.rules import RuleBasedTriage
from app.repositories.complaint_repository import ComplaintRepository
from app.schemas.complaint import CreateComplaintRequest

logger = logging.getLogger(__name__)

# ── Valid status transitions ──────────────────────────────────────────────────
_VALID_TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = {
    ComplaintStatus.open:        {ComplaintStatus.in_progress, ComplaintStatus.rejected},
    ComplaintStatus.in_progress: {ComplaintStatus.resolved, ComplaintStatus.rejected},
    ComplaintStatus.resolved:    set(),   # terminal
    ComplaintStatus.rejected:    set(),   # terminal
}


class InvalidStatusTransitionError(Exception):
    """Raised when a status transition is not allowed by the state machine."""

    def __init__(self, current: ComplaintStatus, requested: ComplaintStatus) -> None:
        self.current = current
        self.requested = requested
        super().__init__(
            f"Cannot transition from '{current.value}' to '{requested.value}'. "
            f"Allowed transitions: {[s.value for s in _VALID_TRANSITIONS[current]]}."
        )


class ComplaintNotFoundError(Exception):
    """Raised when a complaint ID does not exist in the database."""
    pass


class TriageService:
    """
    Orchestrates complaint triage, caching, persistence, and state transitions.
    """

    def __init__(
        self,
        session: AsyncSession | None = None,
        provider: TriageProvider | None = None,
        repo: ComplaintRepository | None = None,
    ) -> None:
        self._repo = repo or (ComplaintRepository(session) if session is not None else None)
        self._provider = provider or get_triage_provider()

    # ── Triage & creation ─────────────────────────────────────────────────

    async def create_complaint(self, request: CreateComplaintRequest):
        """
        Triage and persist a new complaint.

        Steps:
          1. Check Redis 24h content-hash cache for duplicate complaint.
          2. On cache miss: execute active provider (with internal fallback).
          3. Save result to Redis content-hash cache.
          4. Persist to PostgreSQL via ComplaintRepository.
        """
        # Step 1: Check Redis content-hash cache
        cached_result = await triage_cache.get(request.text, request.location)
        if cached_result is not None:
            triage_result = cached_result
            triaged_by_str = self._provider.name
            latency_ms = 1
            fallback_error_class = None
            fallback_occurred = False
            logger.info("Triage result served from Redis content-hash cache (1ms)")
        else:
            # Step 2: Execute active TriageProvider in worker thread
            t0 = time.monotonic()
            try:
                triage_result = await asyncio.to_thread(
                    self._provider.triage,
                    request.text,
                    request.location,
                )
                triaged_by_str = getattr(self._provider, "last_triaged_by", self._provider.name)
                fallback_error_class = getattr(self._provider, "last_error_class", None)
                fallback_occurred = triaged_by_str == "rules:fallback"
            except Exception as exc:
                fallback_error_class = type(exc).__name__
                fallback_occurred = True
                fallback = RuleBasedTriage(name="rules:fallback")
                triage_result = fallback.triage(request.text, request.location)
                triaged_by_str = "rules:fallback"

            latency_ms = max(1, int((time.monotonic() - t0) * 1000))

            # Step 3: Cache result in Redis for 24h
            await triage_cache.set(request.text, request.location, triage_result)

        # Normalize triaged_by for PostgreSQL ENUM safety
        db_triaged_by = self._normalize_triaged_by(triaged_by_str)

        category_val = (
            triage_result.category.value
            if isinstance(triage_result.category, ComplaintCategory)
            else str(triage_result.category)
        )

        complaint_data = {
            "text":              request.text,
            "location":          request.location,
            "reporter_contact":  request.reporter_contact,
            "category":          category_val,
            "priority":          triage_result.priority.value,
            "status":            ComplaintStatus.open.value,
            "ai_summary":        triage_result.summary,
            "triaged_by":        db_triaged_by,
            "triage_latency_ms": latency_ms,
        }

        result = await self._repo.create(complaint_data)
        metrics.observe_triage(
            str(result.id),
            getattr(self._provider, "name", "unknown"),
            latency_ms,
            fallback_occurred,
        )
        if fallback_occurred:
            logger.warning(
                "Triage fallback",
                extra={
                    "complaint_id": str(result.id),
                    "provider": getattr(self._provider, "name", "unknown"),
                    "error_class": fallback_error_class or "ProviderFallback",
                },
            )
        # Invalidate the /api/stats 30s cache on every new complaint
        from app.routes.stats import invalidate_stats_cache
        await invalidate_stats_cache()
        return result

    def _normalize_triaged_by(self, raw: str) -> str:
        """Map provider identifier to valid PostgreSQL triaged_by enum value."""
        valid_values = {e.value for e in TriagedBy}
        if raw in valid_values:
            return raw
        if "fallback" in raw:
            return TriagedBy.rules_fallback.value
        if "ollama" in raw:
            return TriagedBy.llm_ollama.value
        if "rules" in raw:
            return TriagedBy.rules.value
        # Simulated or Gemini or default LLM maps to llm:groq
        return TriagedBy.llm_groq.value

    # ── Status transition (state machine) ─────────────────────────────────

    async def update_status(self, complaint_id, new_status: ComplaintStatus):
        """
        Apply a status transition after validating against the state machine.
        """
        complaint = await self._repo.get_by_id(complaint_id)
        if complaint is None:
            raise ComplaintNotFoundError(f"Complaint {complaint_id} not found.")

        current_status = ComplaintStatus(complaint.status)
        allowed = _VALID_TRANSITIONS[current_status]

        if new_status not in allowed:
            raise InvalidStatusTransitionError(current_status, new_status)

        result = await self._repo.update_status(complaint_id, new_status)
        # Invalidate the /api/stats 30s cache on status changes
        from app.routes.stats import invalidate_stats_cache
        await invalidate_stats_cache()
        return result

    # ── Queries ───────────────────────────────────────────────────────────

    async def get_complaint(self, complaint_id):
        complaint = await self._repo.get_by_id(complaint_id)
        if complaint is None:
            raise ComplaintNotFoundError(f"Complaint {complaint_id} not found.")
        return complaint

    async def list_complaints(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        return await self._repo.list_complaints(
            status=status,
            category=category,
            priority=priority,
            page=page,
            page_size=page_size,
        )
