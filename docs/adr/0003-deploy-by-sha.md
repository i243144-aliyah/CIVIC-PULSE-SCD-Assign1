# ADR 0003: Deploy Immutable Images by Commit SHA

## Status

Accepted

## Context

Mutable tags make rollbacks ambiguous and make it difficult to prove which
source revision is running in Kubernetes.

## Decision

The CD workflow publishes backend and frontend images with the Git commit SHA,
then uses `kustomize edit set image` to inject those exact tags into the
production overlay before applying it. `latest` may be published for discovery
but is not used for deployment or rollback.

## Consequences

Rollouts and rollback records identify a reproducible source revision. Registry
retention and image pull access must preserve the referenced SHA for the life of
the operational rollback window.