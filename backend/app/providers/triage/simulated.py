"""
app/providers/triage/simulated.py
─────────────────────────────────
Deterministic fake triage provider for CI and testing.

Zero network access, seeded predictable outputs, configurable failure injection.
"""

from app.core.enums import ComplaintCategory, ComplaintPriority
from app.providers.triage.base import TriageResult
from app.providers.triage.rules import RuleBasedTriage


class SimulatedTriage:
    """
    Deterministic test provider for CI pipelines and automated testing.
    Supports configurable failure injection to test fallback paths.
    """

    def __init__(
        self,
        name: str = "simulated",
        should_raise: bool = False,
        malformed_json: bool = False,
        forced_category: ComplaintCategory | None = None,
        forced_priority: ComplaintPriority | None = None,
    ) -> None:
        self.name = name
        self.should_raise = should_raise
        self.malformed_json = malformed_json
        self.forced_category = forced_category
        self.forced_priority = forced_priority
        self._rules = RuleBasedTriage(name="simulated_inner")

    def triage(self, text: str, location: str) -> TriageResult:
        # Failure injection: Provider error
        if self.should_raise:
            raise RuntimeError("SimulatedTriage: Provider deliberate failure for testing fallback.")

        # Failure injection: Malformed JSON
        if self.malformed_json:
            raise ValueError("SimulatedTriage: Malformed JSON output {unclosed_json: ")

        # If forced fields are set
        if self.forced_category or self.forced_priority:
            base = self._rules.triage(text, location)
            return TriageResult(
                category=self.forced_category or base.category,
                priority=self.forced_priority or base.priority,
                summary=base.summary,
                confidence=1.0,
            )

        # Deterministic default based on text
        result = self._rules.triage(text, location)
        return TriageResult(
            category=result.category,
            priority=result.priority,
            summary=result.summary,
            confidence=1.0,
        )
