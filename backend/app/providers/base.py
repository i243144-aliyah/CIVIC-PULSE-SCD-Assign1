"""
app/providers/base.py
─────────────────────
Abstract interface that every LLM / AI triage provider must implement.

Design rationale
────────────────
The service layer depends on this *protocol* (structural typing), NOT on any
concrete provider class.  This means:
  - Tests can inject a fake/stub provider without mocking internals.
  - Swapping Groq for Ollama (or adding a new provider) requires only a new
    concrete class + a registration entry; the service layer never changes.
  - The Protocol avoids a deep inheritance tree; duck-typing is sufficient.

Any class that exposes `triage(text, location, category)` and
`is_available() -> bool` automatically satisfies the protocol.
"""

from typing import Protocol, runtime_checkable

from app.core.enums import ComplaintCategory, ComplaintPriority


class TriageResult:
    """
    Value object returned by every triage provider.

    Attributes
    ----------
    priority : ComplaintPriority
        Urgency assigned by the provider.
    ai_summary : str | None
        One-line summary (max 140 chars), or None if the provider does
        not generate summaries.
    triaged_by : str
        Discriminator string matching a TriagedBy enum value
        (e.g. "llm:groq", "rules").
    latency_ms : int
        Wall-clock time taken for the triage call, in milliseconds.
    """

    __slots__ = ("priority", "ai_summary", "triaged_by", "latency_ms")

    def __init__(
        self,
        priority: ComplaintPriority,
        triaged_by: str,
        latency_ms: int,
        ai_summary: str | None = None,
    ) -> None:
        self.priority = priority
        self.ai_summary = ai_summary
        self.triaged_by = triaged_by
        self.latency_ms = latency_ms

    def __repr__(self) -> str:
        return (
            f"TriageResult(priority={self.priority!r}, "
            f"triaged_by={self.triaged_by!r}, latency_ms={self.latency_ms})"
        )


@runtime_checkable
class TriageProvider(Protocol):
    """
    Structural protocol for triage providers.

    Implementations: GroqProvider, OllamaProvider, RulesProvider.
    Each lives in its own module under app/providers/.
    """

    async def triage(
        self,
        text: str,
        location: str,
        category: ComplaintCategory,
    ) -> TriageResult:
        """
        Analyse the complaint and return triage metadata.

        Parameters
        ----------
        text     : Raw complaint text (already validated, 10–2000 chars).
        location : Location string (already validated, 3–200 chars).
        category : Pre-classified category from the request.

        Returns
        -------
        TriageResult with priority, optional summary, provider tag, and latency.
        """
        ...

    async def is_available(self) -> bool:
        """
        Health-check the provider.

        Returns True if the provider can currently accept requests.
        The triage service calls this before routing to decide which
        provider to use (primary → fallback → rules).
        """
        ...
