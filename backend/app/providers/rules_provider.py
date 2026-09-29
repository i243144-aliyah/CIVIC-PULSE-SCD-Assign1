"""
app/providers/rules_provider.py
────────────────────────────────
Rule-based triage provider — zero external dependencies.

This provider assigns priority using a deterministic keyword/category ruleset.
It is used:
  1. As the primary engine when no LLM is configured.
  2. As the final fallback (triaged_by = "rules:fallback") when every LLM
     provider fails or is unavailable.

Because it is purely in-process it always succeeds (is_available returns True)
and has sub-millisecond latency.
"""

import time

from app.core.enums import ComplaintCategory, ComplaintPriority
from app.providers.base import TriageResult

# ── Priority rule table ───────────────────────────────────────────────────────
# Evaluated in declaration order; first match wins.
# Format: (category_set | None, keyword_set | None, assigned_priority)
#   category_set  – match if complaint.category is in this set (None = any)
#   keyword_set   – match if ANY keyword appears in lower-cased complaint text
#                   (None = skip keyword check)
_RULES: list[tuple[set[str] | None, set[str] | None, ComplaintPriority]] = [
    # ── HIGH priority rules ──────────────────────────────────────────────
    # Electrical hazards: exposed wires, live cable, fire risk
    (
        {ComplaintCategory.electricity.value},
        {"exposed", "live wire", "electrocution", "sparking", "fire", "burning"},
        ComplaintPriority.high,
    ),
    # Water emergencies: burst pipes, flooding, contamination
    (
        {ComplaintCategory.water.value},
        {"burst", "flood", "flooding", "contaminated", "sewage overflow", "no water"},
        ComplaintPriority.high,
    ),
    # Road safety hazards
    (
        {ComplaintCategory.roads.value},
        {"pothole", "sinkhole", "collapsed", "accident", "blockage", "unsafe"},
        ComplaintPriority.high,
    ),
    # Sanitation health risk
    (
        {ComplaintCategory.sanitation.value},
        {"overflow", "sewage", "raw sewage", "health hazard", "disease", "smell"},
        ComplaintPriority.high,
    ),
    # Cross-category: any mention of injury or danger
    (
        None,
        {"injury", "injured", "danger", "emergency", "child", "children", "elderly"},
        ComplaintPriority.high,
    ),
    # ── LOW priority rules ───────────────────────────────────────────────
    # Streetlight outage – cosmetic / safety nuisance, not immediate danger
    (
        {ComplaintCategory.streetlights.value},
        None,
        ComplaintPriority.low,
    ),
    # Generic "other" category with no urgent keywords → low
    (
        {ComplaintCategory.other.value},
        None,
        ComplaintPriority.low,
    ),
]

_HIGH_KEYWORDS: set[str] = set()
for _rule in _RULES:
    if _rule[1] and _rule[2] == ComplaintPriority.high:
        _HIGH_KEYWORDS |= _rule[1]


def _apply_rules(
    text: str,
    category: ComplaintCategory,
) -> ComplaintPriority:
    """Evaluate rules sequentially; return the first matching priority."""
    lowered = text.lower()
    for category_set, keyword_set, priority in _RULES:
        # Category filter
        if category_set and category.value not in category_set:
            continue
        # Keyword filter (None means "match regardless of keywords")
        if keyword_set and not any(kw in lowered for kw in keyword_set):
            continue
        return priority
    # Default: normal priority if no specific rule matched
    return ComplaintPriority.normal


class RulesProvider:
    """
    Synchronous, keyword-based triage provider.

    Always available; used as primary engine or fallback.
    The `triaged_by` tag is set by the caller (service layer) to distinguish
    "rules" (primary) from "rules:fallback" (after LLM failure).
    """

    async def triage(
        self,
        text: str,
        location: str,
        category: ComplaintCategory,
        *,
        triaged_by: str = "rules",
    ) -> TriageResult:
        """Apply deterministic ruleset and return a TriageResult."""
        t0 = time.monotonic()
        priority = _apply_rules(text, category)
        latency_ms = int((time.monotonic() - t0) * 1000)
        return TriageResult(
            priority=priority,
            ai_summary=None,    # rules engine does not generate summaries
            triaged_by=triaged_by,
            latency_ms=latency_ms,
        )

    async def is_available(self) -> bool:
        """Rules engine is always available (no external dependencies)."""
        return True
