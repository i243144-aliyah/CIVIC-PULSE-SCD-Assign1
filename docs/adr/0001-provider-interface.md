# ADR 0001: Stable Triage Provider Interface

## Status

Accepted

## Context

Complaint triage must support deterministic rules, tests, local Ollama, and
hosted model providers without coupling the service to one SDK.

## Decision

Use the structural `TriageProvider` protocol and shared `TriageResult` contract
in `backend/app/providers/triage/base.py`. Provider selection remains in
`backend/app/providers/triage/factory.py`; orchestration, caching, and fallback
remain in `backend/app/services/triage_service.py`.

## Consequences

New providers can be tested and selected without changing the HTTP routes. The
service must continue to validate every provider result, and provider-specific
configuration belongs outside the route layer.