"""Initial schema: complaints table with enums, constraints, and indexes.

Revision ID: 0001_initial
Revises: (none – this is the root migration)
Create Date: 2026-09-28 00:00:00.000000 UTC

What this migration does
─────────────────────────
1. Creates four PostgreSQL native ENUM types used by the complaints table.
2. Creates the `complaints` table with all columns, CHECK constraints, and
   server-side defaults.
3. Creates two explicit B-tree indexes (see inline comments for query rationale).

Idempotency
───────────
Alembic tracks applied revisions in the `alembic_version` table, so this
migration will only run once per database regardless of how many times
`alembic upgrade head` is called.

Rollback
────────
`downgrade()` drops the table first (FK safety), then drops all ENUM types.
Running `alembic downgrade base` returns the DB to a pristine empty state.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

# revision identifiers
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─────────────────────────────────────────────────────────────────────
    # Step 1: Create PostgreSQL ENUM types
    #
    # ENUM types must be created BEFORE the table that references them.
    # Using `checkfirst=True` makes each CREATE TYPE call idempotent
    # (no error if the type already exists), which is useful during
    # development when running partial rollbacks and re-applying.
    # ─────────────────────────────────────────────────────────────────────

    complaint_category = sa.Enum(
        "water",
        "electricity",
        "sanitation",
        "roads",
        "streetlights",
        "other",
        name="complaint_category",
    )
    complaint_category.create(op.get_bind(), checkfirst=True)

    complaint_priority = sa.Enum(
        "high",
        "normal",
        "low",
        name="complaint_priority",
    )
    complaint_priority.create(op.get_bind(), checkfirst=True)

    complaint_status = sa.Enum(
        "open",
        "in_progress",
        "resolved",
        "rejected",
        name="complaint_status",
    )
    complaint_status.create(op.get_bind(), checkfirst=True)

    triaged_by = sa.Enum(
        "llm:groq",
        "llm:ollama",
        "rules",
        "rules:fallback",
        name="triaged_by",
    )
    triaged_by.create(op.get_bind(), checkfirst=True)

    # ─────────────────────────────────────────────────────────────────────
    # Step 2: Create the `complaints` table
    # ─────────────────────────────────────────────────────────────────────
    op.create_table(
        "complaints",

        # ── Primary key ───────────────────────────────────────────────────
        # gen_random_uuid() is a PostgreSQL built-in (pg_crypto not required
        # in PG 13+); the application also sets a Python-side default for
        # convenience, but the DB default is the authoritative source.
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Server-generated UUID primary key.",
        ),

        # ── Core complaint text ────────────────────────────────────────────
        sa.Column(
            "text",
            sa.String(2000),
            nullable=False,
            comment="Full complaint text; 10–2000 chars.",
        ),
        sa.Column(
            "location",
            sa.String(200),
            nullable=False,
            comment="Human-readable location; 3–200 chars.",
        ),
        sa.Column(
            "reporter_contact",
            sa.String(255),
            nullable=True,
            comment="Optional reporter contact (email/phone); free-form.",
        ),

        # ── Classification ─────────────────────────────────────────────────
        sa.Column(
            "category",
            sa.Enum(
                "water", "electricity", "sanitation",
                "roads", "streetlights", "other",
                name="complaint_category",
                create_type=False,      # type already created above
            ),
            nullable=False,
            comment="Civic service domain.",
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "high", "normal", "low",
                name="complaint_priority",
                create_type=False,
            ),
            nullable=False,
            comment="Triage-assigned urgency.",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "open", "in_progress", "resolved", "rejected",
                name="complaint_status",
                create_type=False,
            ),
            nullable=False,
            server_default="open",
            comment="Lifecycle state; defaults to 'open'.",
        ),

        # ── AI triage metadata ─────────────────────────────────────────────
        sa.Column(
            "ai_summary",
            sa.String(140),
            nullable=True,
            comment="LLM-generated one-liner; max 140 chars.",
        ),
        sa.Column(
            "triaged_by",
            sa.Enum(
                "llm:groq", "llm:ollama", "rules", "rules:fallback",
                name="triaged_by",
                create_type=False,
            ),
            nullable=False,
            comment="Which triage engine processed this complaint.",
        ),
        sa.Column(
            "triage_latency_ms",
            sa.Integer,
            nullable=False,
            comment="Wall-clock triage duration in milliseconds.",
        ),

        # ── Timestamps (always UTC via AT TIME ZONE 'UTC') ─────────────────
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="UTC insert timestamp; immutable after creation.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="UTC last-modified timestamp; updated on each write.",
        ),

        # ── CHECK constraints ──────────────────────────────────────────────
        # These mirror Pydantic Field constraints so invalid data is rejected
        # at both the application layer AND the database layer.

        # text: 10–2000 characters
        sa.CheckConstraint(
            "char_length(text) >= 10 AND char_length(text) <= 2000",
            name="ck_complaints_text_length",
        ),
        # location: 3–200 characters
        sa.CheckConstraint(
            "char_length(location) >= 3 AND char_length(location) <= 200",
            name="ck_complaints_location_length",
        ),
        # ai_summary: max 140 characters (nullable – NULL is always valid)
        sa.CheckConstraint(
            "ai_summary IS NULL OR char_length(ai_summary) <= 140",
            name="ck_complaints_ai_summary_length",
        ),
        # triage_latency_ms: non-negative integer
        sa.CheckConstraint(
            "triage_latency_ms >= 0",
            name="ck_complaints_triage_latency_non_negative",
        ),
    )

    # ─────────────────────────────────────────────────────────────────────
    # Step 3: Create explicit B-tree indexes
    #
    # These are created AFTER the table so the index creation does not
    # hold a lock on a non-existent table, and so each index can be
    # independently dropped/recreated in future migrations.
    # ─────────────────────────────────────────────────────────────────────

    # Index 1: (status, priority)
    # ──────────────────────────
    # Primary query served:
    #   SELECT * FROM complaints
    #   WHERE status = 'open'
    #   ORDER BY priority    -- 'high' | 'normal' | 'low'
    #
    # Admin dashboards always show open tickets first, sorted by urgency.
    # A composite B-tree index on (status, priority) lets PostgreSQL satisfy
    # both the equality filter on `status` and the sort on `priority` with a
    # single index scan — no full table scan and no separate sort step.
    #
    # Secondary query served:
    #   WHERE status = 'in_progress' AND priority = 'high'
    # (batch processing: fetch high-priority in-progress items)
    op.create_index(
        "ix_complaints_status_priority",
        "complaints",
        ["status", "priority"],
    )

    # Index 2: created_at
    # ───────────────────
    # Primary query served:
    #   SELECT * FROM complaints
    #   WHERE created_at > :cursor
    #   ORDER BY created_at DESC
    #   LIMIT 20
    #
    # Chronological feed and cursor-based pagination both require efficient
    # range scans on `created_at`.  A B-tree index on this timestamptz column
    # makes WHERE created_at > ? + ORDER BY created_at DESC efficient at any
    # table size (PostgreSQL can traverse the B-tree in reverse order).
    #
    # Also accelerates:
    #   WHERE created_at >= '2025-01-01' AND created_at < '2025-02-01'
    # (monthly/weekly reporting aggregations)
    op.create_index(
        "ix_complaints_created_at",
        "complaints",
        ["created_at"],
    )


def downgrade() -> None:
    # Drop indexes first (implicit via DROP TABLE, but explicit for clarity)
    op.drop_index("ix_complaints_created_at",     table_name="complaints")
    op.drop_index("ix_complaints_status_priority", table_name="complaints")

    # Drop the table before the enum types it references
    op.drop_table("complaints")

    # Drop ENUM types (must happen after the table is gone)
    sa.Enum(name="triaged_by").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="complaint_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="complaint_priority").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="complaint_category").drop(op.get_bind(), checkfirst=True)
