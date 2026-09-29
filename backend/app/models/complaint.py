"""
app/models/complaint.py
───────────────────────
SQLAlchemy ORM model for the `complaints` table.

This file describes the *schema only*.  All DDL is applied exclusively via
Alembic migrations; no create_all() call exists anywhere in application code.

Column contract
───────────────
text             10–2000 chars   enforced via CheckConstraint (DB) + Pydantic (app)
location          3–200 chars    enforced via CheckConstraint (DB) + Pydantic (app)
reporter_contact  nullable       no constraint – free-form contact info
ai_summary        nullable       max 140 chars (CheckConstraint + Pydantic)
triage_latency_ms non-negative   CheckConstraint >= 0
created_at/updated_at  timestamptz  always UTC, server-side defaults
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
    TriagedBy,
)

# ── PostgreSQL native ENUM types ──────────────────────────────────────────────
# create_type=False → Alembic migration owns the CREATE TYPE DDL.
_category_enum = ENUM(
    *[e.value for e in ComplaintCategory],
    name="complaint_category",
    create_type=False,
)
_priority_enum = ENUM(
    *[e.value for e in ComplaintPriority],
    name="complaint_priority",
    create_type=False,
)
_status_enum = ENUM(
    *[e.value for e in ComplaintStatus],
    name="complaint_status",
    create_type=False,
)
_triaged_by_enum = ENUM(
    *[e.value for e in TriagedBy],
    name="triaged_by",
    create_type=False,
)


class Complaint(Base):
    """
    Persistent representation of a civic complaint.

    The model is intentionally thin – it carries no business logic.
    Validation lives in Pydantic schemas; business rules live in services.
    """

    __tablename__ = "complaints"

    # ── Primary key ───────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        comment="Server-generated UUID; never supplied by the client.",
    )

    # ── Core complaint fields ─────────────────────────────────────────────
    text: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
        comment="Full complaint text; 10–2000 characters enforced in DB + app.",
    )
    location: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable location; 3–200 characters enforced in DB + app.",
    )
    reporter_contact: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Optional contact info (email, phone, etc.) – no format enforced.",
    )

    # ── Classification ────────────────────────────────────────────────────
    category: Mapped[str] = mapped_column(
        _category_enum,
        nullable=False,
        comment="Civic service domain: water, electricity, sanitation, roads, streetlights, other.",
    )
    priority: Mapped[str] = mapped_column(
        _priority_enum,
        nullable=False,
        comment="Triage-assigned urgency: high, normal, low.",
    )
    status: Mapped[str] = mapped_column(
        _status_enum,
        nullable=False,
        server_default="open",
        comment="Lifecycle state; defaults to 'open' on insert.",
    )

    # ── AI triage metadata ────────────────────────────────────────────────
    ai_summary: Mapped[str | None] = mapped_column(
        String(140),
        nullable=True,
        comment="LLM-generated one-liner summary; max 140 chars enforced in DB + app.",
    )
    triaged_by: Mapped[str] = mapped_column(
        _triaged_by_enum,
        nullable=False,
        comment=(
            "Which engine triaged this complaint: llm:groq | llm:ollama | rules | rules:fallback."
        ),
    )
    triage_latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Wall-clock time (ms) taken by the triage engine; must be >= 0.",
    )

    # ── Timestamps ────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="UTC timestamp of initial insert; immutable after creation.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="UTC timestamp of last modification; updated on every write.",
    )

    # ── DB-level constraints ──────────────────────────────────────────────
    __table_args__ = (
        # Text length: 10–2000 characters (mirrors Pydantic Field constraints)
        CheckConstraint(
            "char_length(text) >= 10 AND char_length(text) <= 2000",
            name="ck_complaints_text_length",
        ),
        # Location length: 3–200 characters
        CheckConstraint(
            "char_length(location) >= 3 AND char_length(location) <= 200",
            name="ck_complaints_location_length",
        ),
        # AI summary length: max 140 characters
        CheckConstraint(
            "ai_summary IS NULL OR char_length(ai_summary) <= 140",
            name="ck_complaints_ai_summary_length",
        ),
        # Triage latency must be non-negative
        CheckConstraint(
            "triage_latency_ms >= 0",
            name="ck_complaints_triage_latency_non_negative",
        ),
        # ── Indexes ───────────────────────────────────────────────────────
        #
        # Index 1: (status, priority)
        #   Serves the primary admin list query:
        #     "give me all OPEN complaints ordered by priority (high first)"
        #   Pattern: WHERE status = 'open' ORDER BY priority
        #   A composite index on (status, priority) allows the planner to
        #   satisfy both the filter and the sort with a single index scan,
        #   avoiding a full table scan + sort.
        Index(
            "ix_complaints_status_priority",
            "status",
            "priority",
        ),
        #
        # Index 2: created_at
        #   Serves chronological feed queries and cursor-based pagination:
        #     "complaints created after <cursor>" / "latest 20 complaints"
        #   A B-tree on created_at makes range scans (WHERE created_at > ?)
        #   and ORDER BY created_at DESC efficient even at millions of rows.
        Index(
            "ix_complaints_created_at",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Complaint id={self.id!s:.8} category={self.category} "
            f"status={self.status} priority={self.priority}>"
        )
