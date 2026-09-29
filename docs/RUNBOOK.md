# CivicPulse Deployment Runbook

## Fast imperative rollback

Use this when the immediate priority is restoring the previous ReplicaSet while
the incident is active. The command is intentionally short enough to be the
3 a.m. answer:

```sh
kubectl rollout undo deployment/backend -n civicpulse
kubectl rollout status deployment/backend -n civicpulse --timeout=180s
kubectl get pods -n civicpulse -l app.kubernetes.io/name=backend
```

Repeat the same commands for `deployment/frontend` if the frontend release is
also affected. Record the incident number, operator, timestamp, and resulting
image digest after service is restored.

## Declarative rollback

Use this for the auditable answer. Re-apply the production overlay with the
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

After either rollback, verify readiness and the public route:

```sh
kubectl get pods -n civicpulse
kubectl get hpa -n civicpulse
kubectl rollout history deployment/backend -n civicpulse
curl --fail --header 'Host: civicpulse.example.com' https://<ingress-address>/health
```

If the imperative rollback resolves the incident, follow up with the
declarative rollback before closing it. Preserve the failed SHA, restored SHA,
kubectl output, and smoke-test result in the incident record.