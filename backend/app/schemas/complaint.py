"""
app/schemas/complaint.py
────────────────────────
Pydantic v2 request/response schemas for the Complaint resource.

Layer contract
──────────────
These schemas live at the *boundary* between HTTP (routes layer) and the
application interior (services / repositories).  They:
  - Validate and coerce inbound JSON (CreateComplaintRequest)
  - Carry validated data INTO the service layer (no ORM objects cross the
    HTTP boundary in either direction)
  - Serialize ORM model instances OUT to JSON responses (ComplaintResponse)

Crucially, schemas do NOT contain business logic; they only enforce shape
and range constraints that are also enforced at the DB level via
CheckConstraints in the ORM model.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
    TriagedBy,
)


class CreateComplaintRequest(BaseModel):
    """
    Body accepted by POST /api/complaints.

    Category is optional because the AI triage engine reads the free text and
    determines the category automatically. If provided, it can be used as a hint.
    All length constraints mirror the DB CheckConstraints in the Complaint model.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Full description of the complaint (10–2000 characters).",
        examples=["There is a burst water pipe flooding the main street corner."],
    )
    location: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Human-readable location of the problem (3–200 characters).",
        examples=["Sector 4, Block B, near the roundabout"],
    )
    reporter_contact: str | None = Field(
        default=None,
        max_length=255,
        description="Optional contact info for the reporter (email, phone, etc.).",
        examples=["jane.doe@example.com"],
    )
    category: ComplaintCategory | None = Field(
        default=None,
        description="Optional domain; if omitted, AI triage engine classifies the text.",
    )


class ComplaintResponse(BaseModel):
    """
    Full complaint representation returned by the API.

    Uses `from_attributes=True` so SQLAlchemy ORM instances can be passed
    directly to `ComplaintResponse.model_validate(orm_instance)`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    location: str
    reporter_contact: str | None
    category: ComplaintCategory
    priority: ComplaintPriority
    status: ComplaintStatus
    ai_summary: str | None = Field(
        default=None,
        max_length=140,
        description="LLM-generated one-line summary (max 140 chars).",
    )
    triaged_by: TriagedBy
    triage_latency_ms: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class ComplaintListResponse(BaseModel):
    """Paginated list of complaints."""

    items: list[ComplaintResponse]
    total: int
    page: int
    page_size: int


class UpdateComplaintStatusRequest(BaseModel):
    """Body accepted by PATCH /complaints/{id}/status."""

    status: ComplaintStatus = Field(
        ...,
        description="New lifecycle status for the complaint.",
    )
