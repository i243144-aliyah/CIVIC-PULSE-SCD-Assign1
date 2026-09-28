"""
Integration tests for Complaints API endpoints, fallback resilience, and health probes.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.complaint import Complaint
from app.providers.triage.simulated import SimulatedTriage
from app.routes.complaints import _get_service
from app.services.triage_service import TriageService


class FakeComplaintRepository:
    """Mock repository allowing API integration tests to run without active PostgreSQL."""

    def __init__(self) -> None:
        self.storage: dict[uuid.UUID, Complaint] = {}

    async def create(self, data: dict[str, Any]) -> Complaint:
        now = datetime.now(timezone.utc)
        complaint = Complaint(
            id=uuid.uuid4(),
            text=data["text"],
            location=data["location"],
            reporter_contact=data.get("reporter_contact"),
            category=data["category"],
            priority=data["priority"],
            status=data.get("status", "open"),
            ai_summary=data.get("ai_summary"),
            triaged_by=data["triaged_by"],
            triage_latency_ms=data["triage_latency_ms"],
            created_at=now,
            updated_at=now,
        )
        self.storage[complaint.id] = complaint
        return complaint

    async def get_by_id(self, complaint_id: uuid.UUID) -> Complaint | None:
        return self.storage.get(complaint_id)

    async def list_complaints(self, **kwargs) -> tuple[list[Complaint], int]:
        items = list(self.storage.values())
        return items, len(items)


@pytest.mark.asyncio
async def test_health_liveness_probe_does_not_touch_db():
    """Verify /health returns 200 independently of database status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_meta_providers_endpoint():
    """Verify /api/meta/providers returns active provider and cache metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/meta/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_provider" in data
        assert "cache" in data
        assert "hit_rate" in data["cache"]


@pytest.mark.asyncio
async def test_fallback_when_provider_always_raises():
    """
    CRITICAL ASSIGNMENT REQUIREMENT:
    'Write this test if you write no other: given a provider that always raises,
    POST /api/complaints still returns 201 and triaged_by == "rules:fallback".'
    """
    # Create failing simulated provider
    failing_provider = SimulatedTriage(should_raise=True)
    fake_repo = FakeComplaintRepository()

    # Dependency override to inject failing provider into TriageService
    async def override_get_service():
        yield TriageService(repo=fake_repo, provider=failing_provider)

    app.dependency_overrides[_get_service] = override_get_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "text": "Broken water main gushing high pressure water into living room",
                "location": "Sector 9, Plot 44",
                "reporter_contact": "citizen@test.com",
            }
            resp = await client.post("/api/complaints", json=payload)

            assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert data["triaged_by"] == "rules:fallback"
            assert data["category"] == "water"
            assert data["priority"] == "high"
            assert len(data["ai_summary"]) <= 140
    finally:
        app.dependency_overrides.pop(_get_service, None)


@pytest.mark.asyncio
async def test_post_complaint_simulated_success():
    """Verify regular complaint submission succeeds with 201 and valid schema."""
    sim_provider = SimulatedTriage()
    fake_repo = FakeComplaintRepository()

    async def override_get_service():
        yield TriageService(repo=fake_repo, provider=sim_provider)

    app.dependency_overrides[_get_service] = override_get_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "text": "Deep pothole in asphalt near school crossing causing traffic accidents",
                "location": "School Road near gate 2",
            }
            resp = await client.post("/api/complaints", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["category"] == "roads"
            assert data["status"] == "open"
            assert data["triage_latency_ms"] >= 0
    finally:
        app.dependency_overrides.pop(_get_service, None)
