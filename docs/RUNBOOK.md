# CivicPulse Deployment Runbook

## Declarative rollback

Use this declarative rollback path to restore the production overlay to the
previous immutable SHA so the desired state in Git and the cluster agree.

```sh
export PREVIOUS_SHA="<previous-successful-github-sha>"
export IMAGE_NAMESPACE="ghcr.io/<owner>/<repository>"

cd k8s/overlays/prod
kustomize edit set image \
  backend="${IMAGE_NAMESPACE}/civicpulse-backend:${PREVIOUS_SHA}" \
  frontend="${IMAGE_NAMESPACE}/civicpulse-frontend:${PREVIOUS_SHA}"
kubectl apply -k .
kubectl rollout status deployment/backend -n civicpulse --timeout=180s
kubectl rollout status deployment/frontend -n civicpulse --timeout=180s
```

The `<previous-successful-github-sha>` placeholder must be replaced with the
SHA recorded from the last successful `Continuous Deployment` run. Never use
`latest` for a rollback. Commit the resulting Kustomize change, or use the
same image substitutions in a reviewed deployment overlay, so the rollback
has an auditable Git history.

## Verification

After the declarative rollback, verify readiness and the public route:

```sh
kubectl get pods -n civicpulse
kubectl get hpa -n civicpulse
kubectl rollout history deployment/backend -n civicpulse
  curl --fail --header 'Host: civicpulse.example.com' https://<ingress-address>/api/meta/providers
```

Preserve the failed SHA, restored SHA,
kubectl output, and smoke-test result in the incident record.

## Troubleshooting matrix

| Symptom | Checks | Remediation |
| --- | --- | --- |
| Backend cannot connect to PostgreSQL | `kubectl get pods -n civic-pulse`; `kubectl logs statefulset/postgres -n civic-pulse`; verify `DATABASE_URL` in the backend secret | Restore the database pod or correct the secret, then restart the backend deployment and wait for readiness. |
| Redis cache evictions or repeated triage misses | `kubectl logs deployment/cache -n civic-pulse`; `kubectl exec -n civic-pulse deploy/cache -- redis-cli INFO stats`; inspect memory policy and volume state | Confirm the cache volume and memory limit, increase capacity if eviction is expected to be lower, and invalidate stale keys only after confirming database health. |
| HPA thrashing between replicas | `kubectl describe hpa -n civic-pulse`; `kubectl top pods -n civic-pulse`; inspect CPU requests and stabilization windows | Check for noisy load or undersized requests, adjust HPA targets and stabilization windows through a reviewed manifest, then observe two scaling periods before closing the incident. |

For every troubleshooting action, record the namespace, UTC timestamp, command
output, image SHA, and resulting rollout state in the incident record.