"""In-process request and triage observability primitives."""

from collections import deque
from threading import Lock
from typing import Any


class ApplicationMetrics:
    """Thread-safe counters and histograms exported in Prometheus text format."""

    _BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: dict[tuple[str, int], int] = {}
        self._request_histogram = self._new_histogram()
        self._triage_histogram = self._new_histogram()
        self._fallbacks = 0
        self._outcomes: deque[dict[str, Any]] = deque(maxlen=20)

    @classmethod
    def _new_histogram(cls) -> dict[str, Any]:
        return {"buckets": [0] * len(cls._BUCKETS), "count": 0, "sum": 0.0}

    def observe_request(self, method: str, status_code: int, seconds: float) -> None:
        with self._lock:
            key = (method, status_code)
            self._requests[key] = self._requests.get(key, 0) + 1
            self._observe(self._request_histogram, seconds)

    def observe_triage(
        self, complaint_id: str, provider: str, latency_ms: int, fallback: bool
    ) -> None:
        with self._lock:
            self._observe(self._triage_histogram, latency_ms / 1000)
            if fallback:
                self._fallbacks += 1
            self._outcomes.appendleft(
                {
                    "complaint_id": complaint_id,
                    "provider": provider,
                    "latency_ms": latency_ms,
                    "fallback": "yes" if fallback else "no",
                }
            )

    @classmethod
    def _observe(cls, histogram: dict[str, Any], value: float) -> None:
        histogram["count"] += 1
        histogram["sum"] += value
        for index, upper_bound in enumerate(cls._BUCKETS):
            if value <= upper_bound:
                histogram["buckets"][index] += 1
                break

    def recent_outcomes(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._outcomes)

    def prometheus_text(self) -> str:
        with self._lock:
            lines = [
                "# HELP http_requests_total Total HTTP requests.",
                "# TYPE http_requests_total counter",
            ]
            for (method, status_code), count in sorted(self._requests.items()):
                lines.append(
                    f'http_requests_total{{method="{method}",status="{status_code}"}} {count}'
                )
            self._append_histogram(lines, "http_request_duration_seconds", self._request_histogram)
            self._append_histogram(lines, "triage_duration_seconds", self._triage_histogram)
            lines.extend(
                (
                    "# HELP triage_fallbacks_total Total triage provider fallbacks.",
                    "# TYPE triage_fallbacks_total counter",
                    f"triage_fallbacks_total {self._fallbacks}",
                )
            )
            return "\n".join(lines) + "\n"

    @classmethod
    def _append_histogram(cls, lines: list[str], name: str, histogram: dict[str, Any]) -> None:
        lines.extend(
            (
                f"# HELP {name} Observed {name.replace('_', ' ')}.",
                f"# TYPE {name} histogram",
            )
        )
        cumulative = 0
        for index, upper_bound in enumerate(cls._BUCKETS):
            cumulative += histogram["buckets"][index]
            lines.append(f'{name}_bucket{{le="{upper_bound:g}"}} {cumulative}')
        lines.append(f'{name}_bucket{{le="+Inf"}} {histogram["count"]}')
        lines.append(f"{name}_sum {histogram['sum']:.6f}")
        lines.append(f"{name}_count {histogram['count']}")


metrics = ApplicationMetrics()
