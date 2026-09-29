"""
app/providers/triage/base.py
────────────────────────────
Abstract structural protocol and contract for all triage providers.

Every concrete provider (LLM, Ollama, Rules, Simulated) must implement:
  - name: str
  - triage(self, text: str, location: str) -> TriageResult
"""

from typing import Protocol, runtime_checkable

from app.schemas.triage import TriageResult


@runtime_checkable
class TriageProvider(Protocol):
    """
    Structural protocol for complaint triage providers.

    Conforming providers:
      - LLMTriage (hosted LLM: Groq / Gemini)
      - OllamaTriage (local offline container)
      - RuleBasedTriage (deterministic keyword fallback)
      - SimulatedTriage (deterministic fake for CI & testing)
    """

    name: str

    def triage(self, text: str, location: str) -> TriageResult:
        """
        Triage the complaint text and location into structured categorization.

        Parameters
        ----------
        text : str
            Full complaint description.
        location : str
            Physical location of the incident.

        Returns
        -------
        TriageResult
            Validated category, priority, summary (<=140 chars), and confidence.
        """
        ...
