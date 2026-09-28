"""
Integration tests for Complaints API endpoints, fallback resilience, and health probes.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import JSONLogFormatter, app, request_id_context
from app.models.complaint import Complaint
from app.providers.triage.simulated import SimulatedTriage
from app.routes import health as health_routes
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
        for key in ("status", "category", "priority"):
            if kwargs.get(key) is not None:
                items = [item for item in items if getattr(item, key) == kwargs[key]]
        total = len(items)
        offset = (kwargs.get("page", 1) - 1) * kwargs.get("page_size", 20)
        return items[offset : offset + kwargs.get("page_size", 20)], total

    async def update_status(self, complaint_id: uuid.UUID, new_status: Any) -> Complaint:
        complaint = self.storage[complaint_id]
        complaint.status = new_status.value
        complaint.updated_at = datetime.now(timezone.utc)
        return complaint


def test_json_log_formatter_includes_request_context_and_fallback_fields():
    token = request_id_context.set("trace-123")
    try:
        record = logging.LogRecord(
            "test", logging.WARNING, __file__, 1, "Triage fallback", (), None
        )
        record.complaint_id = "complaint-456"
        record.provider = "simulated"
        record.error_class = "RuntimeError"
        payload = json.loads(JSONLogFormatter().format(record))
        assert payload["request_id"] == "trace-123"
        assert payload["complaint_id"] == "complaint-456"
        assert payload["provider"] == "simulated"
        assert payload["error_class"] == "RuntimeError"
    finally:
        request_id_context.reset(token)


@pytest.mark.asyncio
async def test_health_liveness_probe_does_not_touch_db(monkeypatch):
    """Verify /health returns 200 independently of database status."""
    async def database_probe_must_not_run():
        raise AssertionError("liveness must not probe the database")

    monkeypatch.setattr(health_routes, "check_database_health", database_probe_must_not_run)
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
async def test_fallback_when_provider_always_raises(caplog: pytest.LogCaptureFixture):
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
            warnings = [record for record in caplog.records if record.message == "Triage fallback"]
            assert len(warnings) == 1
            assert warnings[0].complaint_id == data["id"]
            assert warnings[0].provider == "simulated"
            assert warnings[0].error_class == "RuntimeError"
            outcomes = (await client.get("/api/meta/providers")).json()["recent_outcomes"]
            assert outcomes[0]["complaint_id"] == data["id"]
            assert outcomes[0]["fallback"] == "yes"
            assert isinstance(outcomes[0]["latency_ms"], int)
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


@pytest.mark.asyncio
async def test_invalid_post_returns_field_level_400():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/complaints",
            json={"text": "short", "location": "XY"},
        )
    assert response.status_code == 400
    assert any(error["field"] == "body.text" for error in response.json()["detail"])


@pytest.mark.asyncio
async def test_complaint_status_transition_and_conflict():
    fake_repo = FakeComplaintRepository()

    async def override_get_service():
        yield TriageService(repo=fake_repo, provider=SimulatedTriage())

    app.dependency_overrides[_get_service] = override_get_service
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/complaints",
                json={"text": "A damaged road surface causes a deep pothole", "location": "Main Road"},
            )
            complaint_id = created.json()["id"]
            moved = await client.patch(
                f"/api/complaints/{complaint_id}/status", json={"status": "in_progress"}
            )
            rejected = await client.patch(
                f"/api/complaints/{complaint_id}/status", json={"status": "open"}
            )
        assert created.status_code == 201
        assert moved.status_code == 200
        assert moved.json()["status"] == "in_progress"
        assert rejected.status_code == 409
        assert "in_progress" in rejected.json()["detail"]
        assert "open" in rejected.json()["detail"]
    finally:
        app.dependency_overrides.pop(_get_service, None)


@pytest.mark.asyncio
async def test_list_complaints_filters_and_paginates():
    fake_repo = FakeComplaintRepository()

    async def override_get_service():
        yield TriageService(repo=fake_repo, provider=SimulatedTriage())

    app.dependency_overrides[_get_service] = override_get_service
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for index in range(2):
                await client.post(
                    "/api/complaints",
                    json={
                        "text": f"Water pipe leak flooding street number {index}",
                        "location": f"North Avenue {index}",
                    },
                )
            response = await client.get(
                "/api/complaints?category=water&status=open&page=2&page_size=1"
            )
            oversized = await client.get("/api/complaints?page_size=101")
        assert response.status_code == 200
        assert response.json()["total"] == 2
        assert len(response.json()["items"]) == 1
        assert response.json()["page"] == 2
        assert oversized.status_code == 400
    finally:
        app.dependency_overrides.pop(_get_service, None)


@pytest.mark.asyncio
async def test_request_id_propagation_and_prometheus_metrics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health_response = await client.get("/health", headers={"X-Request-ID": "test-request-42"})
        metrics_response = await client.get("/metrics")
    assert health_response.headers["X-Request-ID"] == "test-request-42"
    assert metrics_response.status_code == 200
    assert "text/plain" in metrics_response.headers["content-type"]
    assert "# TYPE http_requests_total counter" in metrics_response.text
    assert "# TYPE http_request_duration_seconds histogram" in metrics_response.text
    assert "# TYPE triage_duration_seconds histogram" in metrics_response.text
    assert "triage_fallbacks_total" in metrics_response.text


@pytest.mark.asyncio
async def test_readiness_reports_failed_dependencies(monkeypatch):
    async def database_unavailable():
        return False

    async def redis_unavailable():
        return False

    monkeypatch.setattr(health_routes, "check_database_health", database_unavailable)
    monkeypatch.setattr(health_routes, "check_redis_health", redis_unavailable)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json()["failed_dependencies"] == ["database", "redis"]
