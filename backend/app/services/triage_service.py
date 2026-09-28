"""
app/services/triage_service.py
───────────────────────────────
Triage orchestration service — the heart of the complaint lifecycle.

Layer contract
──────────────
• Receives validated Pydantic schemas from the routes layer.
• Owns all business logic: provider selection, fallback chain, state machine.
• Delegates ALL persistence to ComplaintRepository (never touches SQLAlchemy directly).
• Returns ORM instances (or raises domain exceptions) to the routes layer.

Provider fallback chain
───────────────────────
  1. GroqProvider   (if GROQ_API_KEY is set)
  2. OllamaProvider (if Ollama server is reachable)
  3. RulesProvider  (always succeeds; tagged as "rules" or "rules:fallback")

State machine – valid transitions
──────────────────────────────────
  open  ──→  in_progress  ──→  resolved
  open  ──→  rejected
  in_progress  ──→  rejected
  (terminal states: resolved, rejected → no further transitions allowed)
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ComplaintStatus, TriagedBy
from app.providers.groq_provider import GroqProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.rules_provider import RulesProvider
from app.repositories.complaint_repository import ComplaintRepository
from app.schemas.complaint import CreateComplaintRequest

logger = logging.getLogger(__name__)

# ── Valid status transitions ──────────────────────────────────────────────────
# Maps current_status → set of allowed next statuses.
# The state machine is enforced HERE, not at the DB level, so the error
# message can be descriptive and HTTP 409 can be returned to clients.
_VALID_TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = {
    ComplaintStatus.open:        {ComplaintStatus.in_progress, ComplaintStatus.rejected},
    ComplaintStatus.in_progress: {ComplaintStatus.resolved, ComplaintStatus.rejected},
    ComplaintStatus.resolved:    set(),   # terminal
    ComplaintStatus.rejected:    set(),   # terminal
}


class InvalidStatusTransitionError(Exception):
    """Raised when a status transition is not allowed by the state machine."""

    def __init__(
        self,
        current: ComplaintStatus,
        requested: ComplaintStatus,
    ) -> None:
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
    Orchestrates complaint creation (triage) and status transitions.

    One instance is created per request via FastAPI dependency injection;
    it receives the db session and constructs its own repository.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._repo = ComplaintRepository(session)
        # Providers are constructed once per service instance (per request).
        # In Phase 2 these will be singletons injected via DI.
        self._groq = GroqProvider()
        self._ollama = OllamaProvider()
        self._rules = RulesProvider()

    # ── Triage & creation ─────────────────────────────────────────────────

    async def create_complaint(self, request: CreateComplaintRequest):
        """
        Run triage and persist the new complaint.

        Steps:
          1. Attempt LLM triage via the provider chain.
          2. Fall back to rules engine if all LLMs are unavailable/fail.
          3. Persist via repository and return the ORM instance.
        """
        triage_result = await self._run_triage_chain(
            text=request.text,
            location=request.location,
            category=request.category,
        )
        logger.info(
            "Triage complete: provider=%s priority=%s latency=%dms",
            triage_result.triaged_by,
            triage_result.priority.value,
            triage_result.latency_ms,
        )

        complaint_data = {
            "text":              request.text,
            "location":          request.location,
            "reporter_contact":  request.reporter_contact,
            "category":          request.category.value,
            "priority":          triage_result.priority.value,
            "status":            ComplaintStatus.open.value,
            "ai_summary":        triage_result.ai_summary,
            "triaged_by":        triage_result.triaged_by,
            "triage_latency_ms": triage_result.latency_ms,
        }
        return await self._repo.create(complaint_data)

    async def _run_triage_chain(self, *, text: str, location: str, category):
        """
        Try each provider in order; fall back to rules on failure.

        Returns the first successful TriageResult.
        """
        from app.core.enums import ComplaintCategory  # avoid circular at module level

        # 1. Try Groq
        if await self._groq.is_available():
            try:
                return await self._groq.triage(text, location, category)
            except Exception as exc:
                logger.warning("GroqProvider failed (%s); trying Ollama.", exc)

        # 2. Try Ollama
        if await self._ollama.is_available():
            try:
                return await self._ollama.triage(text, location, category)
            except Exception as exc:
                logger.warning("OllamaProvider failed (%s); falling back to rules.", exc)

        # 3. Rules engine (always succeeds)
        #    Tag as "rules:fallback" if we attempted an LLM above, "rules" otherwise.
        groq_configured = bool(await self._groq.is_available.__func__(self._groq)
                               if False else await self._groq.is_available())
        tag = TriagedBy.rules_fallback.value if (
            await self._groq.is_available() or await self._ollama.is_available()
        ) else TriagedBy.rules.value

        return await self._rules.triage(text, location, category, triaged_by=tag)

    # ── Status transition (state machine) ─────────────────────────────────

    async def update_status(self, complaint_id, new_status: ComplaintStatus):
        """
        Apply a status transition after validating it against the state machine.

        Raises
        ------
        ComplaintNotFoundError         if the complaint does not exist.
        InvalidStatusTransitionError   if the transition is not allowed.
        """
        complaint = await self._repo.get_by_id(complaint_id)
        if complaint is None:
            raise ComplaintNotFoundError(f"Complaint {complaint_id} not found.")

        current_status = ComplaintStatus(complaint.status)
        allowed = _VALID_TRANSITIONS[current_status]

        if new_status not in allowed:
            raise InvalidStatusTransitionError(current_status, new_status)

        return await self._repo.update_status(complaint_id, new_status)

    # ── Queries ───────────────────────────────────────────────────────────

    async def get_complaint(self, complaint_id):
        """Fetch a single complaint; raises ComplaintNotFoundError if absent."""
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
        """Delegate to repository; no business logic on reads."""
        return await self._repo.list_complaints(
            status=status,
            category=category,
            priority=priority,
            page=page,
            page_size=page_size,
        )
