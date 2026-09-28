"""
app/repositories/complaint_repository.py
─────────────────────────────────────────
Persistence layer for the Complaint resource.

Layer contract
──────────────
• This module ONLY performs SQL/ORM operations.
• It does NOT contain business logic, validation, or decisions.
• It receives validated Python objects from the service layer and returns
  ORM instances (or None / lists thereof).
• All SQL is written here; no raw SQL or ORM queries exist anywhere else.

Every public method is async so it can be awaited inside an async service.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ComplaintStatus
from app.models.complaint import Complaint


class ComplaintRepository:
    """
    Data-access object for the `complaints` table.

    Constructor accepts an `AsyncSession` injected by FastAPI's dependency
    system, giving the service layer control over transaction boundaries.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Write operations ──────────────────────────────────────────────────

    async def create(self, data: dict[str, Any]) -> Complaint:
        """
        Insert a new complaint row and return the persisted ORM instance.

        `data` is a plain dict produced by the service layer after triage;
        it must already contain all non-nullable fields including triage
        metadata (priority, triaged_by, triage_latency_ms, etc.).
        """
        complaint = Complaint(**data)
        self._session.add(complaint)
        await self._session.flush()   # sends INSERT; ID is now populated
        await self._session.refresh(complaint)
        return complaint

    async def update_status(
        self, complaint_id: uuid.UUID, new_status: ComplaintStatus
    ) -> Complaint | None:
        """
        Update the `status` column for a single complaint.

        Returns the updated ORM instance, or None if the ID does not exist.
        Uses an explicit UPDATE … RETURNING pattern for atomicity.
        """
        stmt = (
            update(Complaint)
            .where(Complaint.id == complaint_id)
            .values(status=new_status.value, updated_at=datetime.now(timezone.utc))
            .returning(Complaint)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    # ── Read operations ───────────────────────────────────────────────────

    async def get_by_id(self, complaint_id: uuid.UUID) -> Complaint | None:
        """Fetch a single complaint by primary key; returns None if not found."""
        stmt = select(Complaint).where(Complaint.id == complaint_id)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_complaints(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Complaint], int]:
        """
        Return a paginated, filtered list of complaints and the total count.

        Filters are additive (AND).  Pagination is offset-based; cursor
        pagination will be added in a future iteration.

        Returns:
            (items, total) – items for this page and the unfiltered total.
        """
        base_stmt = select(Complaint)

        # Apply optional filters
        if status is not None:
            base_stmt = base_stmt.where(Complaint.status == status)
        if category is not None:
            base_stmt = base_stmt.where(Complaint.category == category)
        if priority is not None:
            base_stmt = base_stmt.where(Complaint.priority == priority)

        # Count query (shares same WHERE clause)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total: int = (await self._session.execute(count_stmt)).scalar_one()

        # Data query – ordered newest first, then paginated
        data_stmt = (
            base_stmt
            .order_by(Complaint.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self._session.execute(data_stmt)).scalars().all()

        return list(rows), total

    async def exists_by_id(self, complaint_id: uuid.UUID) -> bool:
        """Lightweight existence check without loading the full row."""
        stmt = select(func.count()).where(Complaint.id == complaint_id)
        count: int = (await self._session.execute(stmt)).scalar_one()
        return count > 0

    async def get_stats(self) -> dict:
        """
        Compute aggregate statistics across the full complaints table.

        Returns a dict ready to be JSON-serialised for GET /api/stats.
        Uses a single SQL pass (FILTER clauses) so it never table-scans twice.
        """
        from sqlalchemy import case, literal

        total_stmt = select(
            func.count().label("total"),
            func.count().filter(Complaint.status == "open").label("open"),
            func.count().filter(Complaint.status == "in_progress").label("in_progress"),
            func.count().filter(Complaint.status == "resolved").label("resolved"),
            func.count().filter(Complaint.status == "rejected").label("rejected"),
            func.count().filter(Complaint.priority == "high").label("high"),
            func.count().filter(Complaint.priority == "normal").label("normal"),
            func.count().filter(Complaint.priority == "low").label("low"),
            func.count().filter(Complaint.category == "water").label("water"),
            func.count().filter(Complaint.category == "electricity").label("electricity"),
            func.count().filter(Complaint.category == "sanitation").label("sanitation"),
            func.count().filter(Complaint.category == "roads").label("roads"),
            func.count().filter(Complaint.category == "streetlights").label("streetlights"),
            func.count().filter(Complaint.category == "other").label("other"),
            func.avg(Complaint.triage_latency_ms).label("avg_latency_ms"),
        ).select_from(Complaint)

        row = (await self._session.execute(total_stmt)).one()

        return {
            "total": row.total,
            "by_status": {
                "open": row.open,
                "in_progress": row.in_progress,
                "resolved": row.resolved,
                "rejected": row.rejected,
            },
            "by_priority": {
                "high": row.high,
                "normal": row.normal,
                "low": row.low,
            },
            "by_category": {
                "water": row.water,
                "electricity": row.electricity,
                "sanitation": row.sanitation,
                "roads": row.roads,
                "streetlights": row.streetlights,
                "other": row.other,
            },
            "avg_triage_latency_ms": round(float(row.avg_latency_ms or 0), 2),
        }
