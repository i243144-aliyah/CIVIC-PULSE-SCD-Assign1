"""Prometheus metrics endpoint."""

from fastapi import APIRouter, Response

from app.core.observability import metrics

router = APIRouter(tags=["Metrics"])


@router.get("/metrics", include_in_schema=False)
async def get_metrics() -> Response:
    return Response(
        content=metrics.prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )