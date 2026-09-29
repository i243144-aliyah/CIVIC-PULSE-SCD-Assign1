"""
app/core/enums.py
─────────────────
All application-level enumerations.

These are the *single source of truth* for enum values used by:
  - SQLAlchemy ORM models (as PostgreSQL native enums)
  - Pydantic schemas (validation)
  - Alembic migrations (must reference these same names)

Import from here; never redeclare enum values elsewhere.
"""

from enum import StrEnum


class ComplaintCategory(StrEnum):
    """Civic service domain the complaint belongs to."""

    water = "water"
    electricity = "electricity"
    sanitation = "sanitation"
    roads = "roads"
    streetlights = "streetlights"
    other = "other"


class ComplaintPriority(StrEnum):
    """Triage-assigned urgency level."""

    high = "high"
    normal = "normal"
    low = "low"


class ComplaintStatus(StrEnum):
    """Lifecycle state of a complaint."""

    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    rejected = "rejected"


class TriagedBy(StrEnum):
    """
    Identifies which triage engine processed the complaint.

    Values use a colon-separated namespace so the UI / analytics can
    easily group by engine type (llm vs rules) independent of the model.
    """

    llm_groq = "llm:groq"
    llm_ollama = "llm:ollama"
    rules = "rules"
    rules_fallback = "rules:fallback"
