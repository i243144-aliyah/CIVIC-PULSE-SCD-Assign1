# Triage Strategy

## Request flow

Complaint text and location are validated by the Pydantic request schema before
they reach `TriageService`. The service computes a normalized SHA-256 content
hash and checks `app/providers/cache.py` first. A cache hit returns the stored
`TriageResult` without invoking a provider. A miss selects the configured
provider through `app/providers/triage/factory.py`, records latency, stores the
result for 24 hours, and persists the complaint metadata.

## Prompt engineering

The LLM provider uses a fixed system instruction that defines the allowed
category and priority values, requires a short summary, and requires structured
JSON output. User text is placed in a clearly delimited data section. The prompt
explicitly says that instructions inside the complaint are untrusted content;
this prevents a complaint such as "ignore the system prompt" from changing the
classification contract. Pydantic validation is the final boundary: malformed,
unknown, or out-of-range model output is rejected rather than persisted.

## Provider and fallback logic

`TRIAGE_PROVIDER` selects `rules`, `simulated`, `ollama`, or `llm`. The rules
provider is deterministic and offline, making it the operational fallback for
provider timeouts, rate limits, malformed responses, and missing credentials.
The factory keeps provider selection in one place, while the service owns the
fallback and cache sequence. The simulated provider is used by CI and tests so
the suite does not depend on an external model service.

## Latency and cost trade-offs

| Provider | Latency | Cost | Use |
| --- | --- | --- | --- |
| Rules | Low and predictable | None | Default fallback and offline operation |
| Simulated | Low and deterministic | None | Tests and CI |
| Ollama | Depends on local model and warm-up | Infrastructure cost | Private/local inference |
| Hosted LLM | Network and provider latency | Per-request token cost | Higher-quality classification when configured |

The content cache reduces both hosted-model cost and repeated latency. A cached
result is still tied to the normalized text and location, so unrelated reports
do not share classifications. Operators should monitor cache hit rate and model
latency before changing the 24-hour TTL.

## Operational controls

Do not place secrets or raw provider responses in logs. Keep provider API keys in
environment configuration, use `TRIAGE_PROVIDER=simulated` in CI, and review
changes to categories, prompts, and fallback behavior with the provider tests in
`backend/tests/test_triage_providers.py` and the prompt-injection tests.