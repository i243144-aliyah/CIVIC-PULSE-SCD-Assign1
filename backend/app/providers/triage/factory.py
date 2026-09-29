"""
app/providers/triage/factory.py
───────────────────────────────
Factory for selecting the active TriageProvider based on the TRIAGE_PROVIDER env var.
"""

import os
from typing import Any

from app.core.config import settings
from app.providers.triage.base import TriageProvider
from app.providers.triage.llm import LLMTriage
from app.providers.triage.ollama import OllamaTriage
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage


def get_triage_provider(provider_name: str | None = None, **kwargs: Any) -> TriageProvider:
    """
    Instantiate and return the requested TriageProvider implementation.

    Parameters
    ----------
    provider_name : str | None
        Name of the provider: 'llm', 'ollama', 'rules', or 'simulated'.
        If None, resolves from the TRIAGE_PROVIDER environment variable or settings.

    Returns
    -------
    TriageProvider
        An instance implementing the TriageProvider protocol.
    """
    name = (
        (provider_name or os.getenv("TRIAGE_PROVIDER") or settings.triage_provider or "rules")
        .lower()
        .strip()
    )

    if name in {"llm", "llmtriage", "groq", "gemini"}:
        return LLMTriage(**kwargs)
    elif name in {"ollama", "ollamatriage"}:
        return OllamaTriage(**kwargs)
    elif name in {"rules", "rulebasedtriage", "rule_based"}:
        return RuleBasedTriage(**kwargs)
    elif name in {"simulated", "simulatedtriage", "fake", "test"}:
        return SimulatedTriage(**kwargs)
    else:
        raise ValueError(
            f"Unknown TRIAGE_PROVIDER '{name}'. "
            "Supported values: 'llm', 'ollama', 'rules', 'simulated'."
        )
