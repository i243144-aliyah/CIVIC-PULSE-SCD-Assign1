"""
Tests for TriageProvider implementations and resilience patterns.
"""

import pytest

from app.core.enums import ComplaintCategory, ComplaintPriority
from app.providers.triage.base import TriageProvider, TriageResult
from app.providers.triage.factory import get_triage_provider
from app.providers.triage.llm import LLMTriage
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage


def test_triage_result_schema_constraints():
    """Verify TriageResult enforces required schema and length constraints."""
    result = TriageResult(
        category=ComplaintCategory.water,
        priority=ComplaintPriority.high,
        summary="A" * 200,  # Should be automatically truncated to <= 140
        confidence=0.95,
    )
    assert len(result.summary) <= 140
    assert result.confidence == 0.95
    assert result.category == ComplaintCategory.water
    assert result.priority == ComplaintPriority.high


def test_rule_based_triage_categories():
    """Verify RuleBasedTriage accurately detects civic categories from text."""
    provider = RuleBasedTriage()
    assert isinstance(provider, TriageProvider)

    # Water test
    r_water = provider.triage(
        "There is a burst water pipe flooding the street outside my house",
        "Oak Avenue",
    )
    assert r_water.category == ComplaintCategory.water
    assert r_water.priority == ComplaintPriority.high

    # Electricity test
    r_elec = provider.triage(
        "An electric transformer is sparking with exposed live wires hanging down",
        "Market Road",
    )
    assert r_elec.category == ComplaintCategory.electricity
    assert r_elec.priority == ComplaintPriority.high

    # Sanitation test
    r_san = provider.triage(
        "Garbage bins are overflowing with rotting rubbish and rats everywhere",
        "High Street",
    )
    assert r_san.category == ComplaintCategory.sanitation

    # Roads test
    r_road = provider.triage(
        "Massive pothole in the asphalt near the roundabout damaging car tyres",
        "Ring Road",
    )
    assert r_road.category == ComplaintCategory.roads

    # Streetlights test
    r_light = provider.triage(
        "Streetlight lamp has been dark and unlit for two weeks",
        "Pine Close",
    )
    assert r_light.category == ComplaintCategory.streetlights


def test_simulated_triage_deterministic():
    """Verify SimulatedTriage returns deterministic valid results for CI."""
    sim = SimulatedTriage()
    assert isinstance(sim, TriageProvider)
    assert sim.name == "simulated"

    result = sim.triage("Flooded street with leaking water main", "Sector 7")
    assert isinstance(result, TriageResult)
    assert result.category == ComplaintCategory.water
    assert result.confidence == 1.0


def test_simulated_triage_failure_injection():
    """Verify SimulatedTriage configurable failure injection raises as requested."""
    sim_raise = SimulatedTriage(should_raise=True)
    with pytest.raises(RuntimeError, match="deliberate failure"):
        sim_raise.triage("Water leak", "Downtown")

    sim_malformed = SimulatedTriage(malformed_json=True)
    with pytest.raises(ValueError, match="Malformed JSON"):
        sim_malformed.triage("Water leak", "Downtown")


def test_factory_provider_selection(monkeypatch):
    """Verify factory dynamically selects providers based on TRIAGE_PROVIDER env var."""
    monkeypatch.setenv("TRIAGE_PROVIDER", "rules")
    p_rules = get_triage_provider()
    assert isinstance(p_rules, RuleBasedTriage)

    monkeypatch.setenv("TRIAGE_PROVIDER", "simulated")
    p_sim = get_triage_provider()
    assert isinstance(p_sim, SimulatedTriage)

    monkeypatch.setenv("TRIAGE_PROVIDER", "llm")
    p_llm = get_triage_provider()
    assert isinstance(p_llm, LLMTriage)

    with pytest.raises(ValueError, match="Unknown TRIAGE_PROVIDER"):
        get_triage_provider("non_existent_engine")


def test_llm_triage_fallback_on_unconfigured_api_key():
    """
    Verify LLMTriage gracefully catches unconfigured keys and falls back to
    RuleBasedTriage with triaged_by = 'rules:fallback'.
    """
    provider = LLMTriage()
    # Force call with empty keys to trigger fallback
    result = provider.triage("Severe sewage overflow outside hospital", "Main St")

    assert isinstance(result, TriageResult)
    assert result.category == ComplaintCategory.sanitation
    assert result.priority == ComplaintPriority.high
    assert provider.last_triaged_by == "rules:fallback"
