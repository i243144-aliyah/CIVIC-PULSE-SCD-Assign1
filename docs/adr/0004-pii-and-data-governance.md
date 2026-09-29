# ADR 0004: PII and Data Governance

## Status

Accepted

## Context

Complaints may include reporter contact details and free-form text that can
contain personal or sensitive information. Triage providers and operational logs
must not become an uncontrolled copy of that data.

## Decision

Persist only the fields defined by the complaint schema, keep contact data out of
logs and prompts unless required for classification, and never commit secrets or
real production records. Provider credentials come from environment/secret
configuration. Cache entries use a content hash key and validated triage result;
operators must apply the configured Redis TTL and access controls.

## Consequences

The application has a clear minimum-data boundary, but retention, deletion, and
access-review procedures remain operational responsibilities. Any new field or
provider integration requires a privacy review and corresponding test coverage.