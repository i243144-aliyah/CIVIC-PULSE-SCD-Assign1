# HPA/VPA Load-Test Evidence

> Evidence template only. Replace the placeholders with output captured from the target cluster; do not treat this file as proof of a completed cluster run.

## Test Context

| Field | Value |
|---|---|
| Cluster / Kubernetes version | `<cluster name and version>` |
| Node count and instance types | `<nodes>` |
| Metrics Server version/status | `<version; APIService available>` |
| VPA recommender/CRD version | `<version; autoscaling.k8s.io/v1 available>` |
| Image tags | `<backend and frontend immutable tags>` |
| Test start/end (UTC) | `<timestamps>` |
| k6 version and command | `<version and command>` |
| k6 result / thresholds | `<summary and pass/fail>` |

Suggested execution:

```sh
kubectl exec -n civicpulse deployment/backend -- alembic upgrade head
kubectl port-forward -n civicpulse svc/backend 8000:8000
# In another terminal:
k6 run -e TARGET_URL=http://localhost:8000 load/k6-script.js
```

The script runs for ten minutes by default with sustained POST `/api/complaints`, GET `/api/complaints`, and GET `/api/stats` traffic. Use `-e DURATION=15s` for a quick smoke test. `TARGET_URL` takes precedence over `BASE_URL` and defaults to `http://localhost:8000`. Its complaint arrival rate is limited to 12/minute, below the default per-IP 30/minute API limiter. Ensure the k6 executable is installed and available on `PATH` before running; this environment's working binary is `/usr/local/bin/k6`.

## Five-Step VPA Iterative Loop

1. **Observe:** Apply the backend VPA in `Off` mode and run representative load long enough to capture steady-state CPU and memory. Save pod metrics and application latency/error summaries.
2. **Recommend:** Capture `kubectl describe vpa backend -n civicpulse` and the recommendation targets for CPU/memory requests and limits. VPA `Off` reports advice only; it does not mutate the Deployment.
3. **Compare:** Record the current manifest requests/limits beside the VPA target recommendation. Review headroom, node allocatable capacity, HPA CPU utilization implications, and restart risk with the service owner.
4. **Apply manually:** Update reviewed requests/limits through a change to the Deployment/Kustomize source while leaving `updateMode: Off`. Roll out using the configured `maxSurge: 1`, `maxUnavailable: 0` strategy.
5. **Re-test:** Re-run the same k6 workload, compare latency/error rates and resource usage, and retain the before/after recommendation and chart artifacts. Repeat the loop if results remain outside the service SLO.

## Original and Updated Resources

The checked-in backend Deployment baseline is `100m` CPU / `128Mi` memory requests and `500m` CPU / `512Mi` memory limits.

| Container | CPU request | Memory request | CPU limit | Memory limit | Evidence/revision |
|---|---:|---:|---:|---:|---|
| Original backend | 100m | 128Mi | 500m | 512Mi | `k8s/base/backend-deployment.yaml` |
| VPA recommendation | `<record target>` | `<record target>` | `<record target>` | `<record target>` | `<kubectl describe vpa output>` |
| Manually updated backend | `<record applied>` | `<record applied>` | `<record applied>` | `<record applied>` | `<Git commit/deployment revision>` |

## HPA Scaling Evidence

Configured HPA policy: CPU average utilization target `60%`, minimum `2` replicas, maximum `10`, and scale-down stabilization window `300s`.

- `kubectl get hpa backend -n civicpulse -w` capture: `<attach or link chart/log>`
- `kubectl describe hpa backend -n civicpulse`: `<attach output>`
- Replica count before / peak / after test: `<values and timestamps>`
- CPU utilization before / peak / after test: `<values and timestamps>`
- Scaling events and stabilization observations: `<notes>`
- Request latency / error comparison: `<before and after summaries>`

## Artifacts

- k6 summary JSON or HTML report: `<artifact path/link>`
- HPA CPU/replica chart: `<artifact path/link>`
- VPA recommendation capture: `<artifact path/link>`
- Pod logs and rollout status: `<artifact path/link>`
- Exceptions or deviations: `<notes>`