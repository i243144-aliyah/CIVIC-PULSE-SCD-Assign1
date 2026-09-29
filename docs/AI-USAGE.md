# AI Usage Disclosure

## Development assistance

AI assistance was used during implementation for codebase navigation, workflow
scaffolding, documentation drafting, and review of test and deployment paths.
All generated changes were inspected against the repository's actual FastAPI,
React, Compose, and Kubernetes code before inclusion.

## Runtime AI behavior

CivicPulse can use a hosted LLM or local Ollama provider for complaint triage.
The selected provider is controlled by `TRIAGE_PROVIDER`; the deterministic
rules provider is the fallback and the simulated provider is used for CI. AI
output is validated through the shared `TriageResult` schema before persistence.

## Human verification

AI suggestions were not treated as authoritative for security, privacy, or
deployment decisions. The final implementation was checked with backend tests,
frontend tests/typechecking where the local toolchain was available, Compose
configuration validation, workflow inspection, and Kubernetes manifest review.
Secrets, credentials, and production personal data were not supplied to an AI
system.