"""
app/providers/groq_provider.py
────────────────────────────────
Groq LLM triage provider (Phase 2 stub).

This module defines the interface and structure for the Groq integration.
The actual HTTP call to the Groq API is wired up in Phase 2 when
`GROQ_API_KEY` is configured.  Until then `is_available()` returns False
and the service layer will route to the next provider.

Separation of concerns:
  • This file owns ALL Groq-specific HTTP logic.
  • The service layer never imports httpx or constructs Groq payloads.
"""

import time

import httpx

from app.core.config import settings
from app.core.enums import ComplaintCategory, ComplaintPriority
from app.providers.base import TriageResult

_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "llama3-8b-8192"
_TIMEOUT_SECONDS = 10.0

_SYSTEM_PROMPT = """You are a civic complaint triage assistant.
Analyse the complaint and respond with a JSON object containing exactly two keys:
  "priority": one of "high", "normal", or "low"
  "summary":  a single sentence (≤140 chars) describing the core issue

Respond ONLY with valid JSON. No prose, no markdown.
"""


def _parse_priority(raw: str) -> ComplaintPriority:
    """Map raw string → ComplaintPriority with a safe fallback."""
    mapping = {
        "high": ComplaintPriority.high,
        "normal": ComplaintPriority.normal,
        "low": ComplaintPriority.low,
    }
    return mapping.get(raw.lower().strip(), ComplaintPriority.normal)


class GroqProvider:
    """
    Triage provider backed by the Groq inference API.

    Requires `GROQ_API_KEY` to be set in the environment.
    Falls back gracefully: if the API key is absent or the HTTP call fails,
    `is_available()` returns False and the service routes to the next provider.
    """

    def __init__(self) -> None:
        self._api_key = settings.groq_api_key

    async def is_available(self) -> bool:
        """Return True only when an API key is configured."""
        return bool(self._api_key)

    async def triage(
        self,
        text: str,
        location: str,
        category: ComplaintCategory,
    ) -> TriageResult:
        """
        Send the complaint to Groq and parse the structured response.

        Raises httpx.HTTPError on network / API failure so the service layer
        can catch it and fall back to the next provider.
        """
        import json  # lazy import – avoids cost when not used

        user_message = (
            f"Category: {category.value}\n"
            f"Location: {location}\n"
            f"Complaint: {text}"
        )
        payload = {
            "model": _MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            "temperature": 0.1,
            "max_tokens": 100,
            "response_format": {"type": "json_object"},
        }

        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = client.post(  # type: ignore[assignment]
                _GROQ_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
            # Raise on 4xx/5xx
            response.raise_for_status()  # type: ignore[union-attr]

        latency_ms = int((time.monotonic() - t0) * 1000)
        body = json.loads(response.text)  # type: ignore[union-attr]
        content = json.loads(body["choices"][0]["message"]["content"])

        priority = _parse_priority(content.get("priority", "normal"))
        summary: str | None = content.get("summary")
        if summary and len(summary) > 140:
            summary = summary[:137] + "..."

        return TriageResult(
            priority=priority,
            ai_summary=summary,
            triaged_by="llm:groq",
            latency_ms=latency_ms,
        )
