# ADR 0002: Frontend Runtime API Configuration

## Status

Accepted

## Context

The same frontend image must work in local Compose, Kubernetes, and production
without rebuilding JavaScript for each API hostname.

## Decision

Use relative `/api` requests from `frontend/src/api.ts` and route them through
the Vite development proxy or the Nginx/Kubernetes ingress configuration. Keep
environment-specific routing outside compiled application code.

## Consequences

One image can be promoted between environments and browser same-origin behavior
avoids duplicated CORS configuration. Local development requires the proxy and
production requires the frontend and backend paths to remain aligned.