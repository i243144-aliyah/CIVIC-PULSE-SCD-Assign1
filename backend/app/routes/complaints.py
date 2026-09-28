"""
app/routes/complaints.py
─────────────────────────
HTTP layer for the Complaint resource.

Layer contract
──────────────
• Parses HTTP inputs (path params, query params, JSON bodies) into Pydantic schemas.
• Injects the service via FastAPI DI; NEVER calls repositories directly.
• Serializes service output (ORM instances) into Pydantic response schemas.
• Handles domain exceptions (ComplaintNotFoundError, InvalidStatusTransitionError)
  and maps them to appropriate HTTP status codes.
• Contains NO business logic – no conditionals beyond error mapping.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.enums import ComplaintCategory, ComplaintPriority, ComplaintStatus
from app.schemas.complaint import (
    ComplaintListResponse,
    ComplaintResponse,
    CreateComplaintRequest,
    UpdateComplaintStatusRequest,
)
from app.services.triage_service import (
    ComplaintNotFoundError,
    InvalidStatusTransitionError,
    TriageService,
)

router = APIRouter(prefix="/complaints", tags=["Complaints"])


# ── Dependency: service instance scoped to this request ───────────────────────
def _get_service(session: AsyncSession = Depends(get_session)) -> TriageService:
    return TriageService(session)


# ── POST /complaints ──────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=ComplaintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new civic complaint",
    description=(
        "Accepts a complaint, runs AI/rules triage to assign priority and "
        "generate an optional summary, then persists the record."
    ),
)
async def create_complaint(
    body: CreateComplaintRequest,
    service: TriageService = Depends(_get_service),
) -> ComplaintResponse:
    complaint = await service.create_complaint(body)
    return ComplaintResponse.model_validate(complaint)


# ── GET /complaints ───────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=ComplaintListResponse,
    summary="List complaints with optional filters",
)
async def list_complaints(
    status_filter: ComplaintStatus | None = Query(
        default=None, alias="status",
        description="Filter by lifecycle status.",
    ),
    category: ComplaintCategory | None = Query(
        default=None,
        description="Filter by service category.",
    ),
    priority: ComplaintPriority | None = Query(
        default=None,
        description="Filter by priority level.",
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page."),
    service: TriageService = Depends(_get_service),
) -> ComplaintListResponse:
    items, total = await service.list_complaints(
        status=status_filter.value if status_filter else None,
        category=category.value if category else None,
        priority=priority.value if priority else None,
        page=page,
        page_size=page_size,
    )
    return ComplaintListResponse(
        items=[ComplaintResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── GET /complaints/{id} ──────────────────────────────────────────────────────
@router.get(
    "/{complaint_id}",
    response_model=ComplaintResponse,
    summary="Get a single complaint by ID",
)
async def get_complaint(
    complaint_id: uuid.UUID,
    service: TriageService = Depends(_get_service),
) -> ComplaintResponse:
    try:
        complaint = await service.get_complaint(complaint_id)
    except ComplaintNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return ComplaintResponse.model_validate(complaint)


# ── PATCH /complaints/{id}/status ─────────────────────────────────────────────
@router.patch(
    "/{complaint_id}/status",
    response_model=ComplaintResponse,
    summary="Transition complaint to a new status",
    description=(
        "Valid transitions: open→in_progress, open→rejected, "
        "in_progress→resolved, in_progress→rejected. "
        "Resolved and rejected are terminal states."
    ),
)
async def update_complaint_status(
    complaint_id: uuid.UUID,
    body: UpdateComplaintStatusRequest,
    service: TriageService = Depends(_get_service),
) -> ComplaintResponse:
    try:
        complaint = await service.update_status(complaint_id, body.status)
    except ComplaintNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return ComplaintResponse.model_validate(complaint)
