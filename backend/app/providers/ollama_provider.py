"""
app/providers/ollama_provider.py
────────────────────────────────
Ollama (local LLM) triage provider (Phase 2 stub).

Connects to a locally-running Ollama instance.  `is_available()` performs a
live health-check against the Ollama API so the service can route accordingly.
"""

import json
import time

import httpx

from app.core.config import settings
from app.core.enums import ComplaintCategory, ComplaintPriority
from app.providers.base import TriageResult

_GENERATE_PATH = "/api/generate"
_MODEL = "llama3"
_TIMEOUT_SECONDS = 30.0  # local inference can be slower than cloud

_PROMPT_TEMPLATE = """You are a civic complaint triage assistant.
Analyse the complaint below and respond with a JSON object containing:
  "priority": one of "high", "normal", or "low"
  "summary":  a single sentence (≤140 chars) describing the core issue

Category: {category}
Location: {location}
Complaint: {text}

Respond ONLY with valid JSON. No prose, no markdown.
"""


def _parse_priority(raw: str) -> ComplaintPriority:
    mapping = {
        "high": ComplaintPriority.high,
        "normal": ComplaintPriority.normal,
        "low": ComplaintPriority.low,
    }
    return mapping.get(raw.lower().strip(), ComplaintPriority.normal)


class OllamaProvider:
    """
    Triage provider backed by a locally-running Ollama instance.

    Requires `OLLAMA_BASE_URL` (default: http://localhost:11434).
    `is_available()` performs a lightweight GET to the Ollama root endpoint.
    """

    def __init__(self) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")

    async def is_available(self) -> bool:
        """
        Return True if the Ollama server responds to a health-check GET.
        Times out after 2 seconds to avoid blocking the request cycle.
        """
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(self._base_url)
                return r.status_code == 200
        except Exception:
            return False

    async def triage(
        self,
        text: str,
        location: str,
        category: ComplaintCategory,
    ) -> TriageResult:
        """
        Send the complaint to local Ollama and parse the structured response.

        Uses the /api/generate endpoint with `stream=false` for simplicity.
        Raises httpx.HTTPError on failure so the service can fall back.
        """
        prompt = _PROMPT_TEMPLATE.format(
            category=category.value,
            location=location,
            text=text,
        )
        payload = {
            "model": _MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{self._base_url}{_GENERATE_PATH}",
                json=payload,
            )
            response.raise_for_status()

        latency_ms = int((time.monotonic() - t0) * 1000)
        body = response.json()
        content = json.loads(body["response"])

        priority = _parse_priority(content.get("priority", "normal"))
        summary: str | None = content.get("summary")
        if summary and len(summary) > 140:
            summary = summary[:137] + "..."

        return TriageResult(
            priority=priority,
            ai_summary=summary,
            triaged_by="llm:ollama",
            latency_ms=latency_ms,
        )
