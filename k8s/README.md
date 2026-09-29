# Kubernetes Deployment

Both Kustomize overlays deploy into the `civicpulse` namespace. The committed Secret contains placeholders only; replace it with a cluster Secret or external secret integration before deploying real workloads. Do not commit live credentials.

Build and review the rendered resources:

```sh
kubectl kustomize k8s/overlays/dev
kubectl kustomize k8s/overlays/prod
```

The production overlay uses `ghcr.io/replace-me/...:replace-me` image references. Update those image mappings in `k8s/overlays/prod/kustomization.yaml` to immutable published tags before applying.

Deploy an overlay:

```sh
docker build -t backend:latest ./backend
docker build -t frontend:latest ./frontend
minikube image load backend:latest
minikube image load frontend:latest
kubectl apply -k k8s/overlays/dev
kubectl rollout status deployment/backend -n civicpulse
kubectl rollout status deployment/frontend -n civicpulse
```

The local image tags must match the dev Deployment references exactly. `minikube image load backend:latest` will not find an image tagged `civicpulse-backend:phase5`; build (or `docker tag`) it as `backend:latest` first. The frontend tag refers to the Nginx runtime stage produced by the frontend Dockerfile, not the Node builder stage.

The Ingress requires an installed controller matching `ingressClassName: nginx`; set the overlay host and DNS to the controller address. HPA recommendations require Metrics Server. The recommender-only VPA resource requires the VPA CRDs/controller (`autoscaling.k8s.io/v1`) installed in the cluster. `backend-vpa` is in `Off` mode and does not mutate pod resources.

The backend Deployment uses a zero-unavailable rolling update, startup/liveness/readiness probes, and a five-second `preStop` delay. The HPA has a two-replica minimum and a ten-replica maximum; the PDB maintains at least one available backend during voluntary disruptions.