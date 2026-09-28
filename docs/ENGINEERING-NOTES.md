# Engineering Notes: Containers and Networking

## Persistent Volumes

| Volume | Service/path | Reason |
|---|---|---|
| `pgdata` | PostgreSQL `/var/lib/postgresql/data` | Keeps complaint records and database state across container replacement, `compose down`, and host restarts. Do not use `compose down -v` when data must survive. |
| `redisdata` | Redis `/data` | Redis runs with `redis-server --appendonly yes`; its append-only file preserves cache/rate-limit state when the Redis container is replaced. Redis remains an operational cache, not the authoritative complaint store. |
| `ollama_models` | Ollama `/root/.ollama` | Stores downloaded model weights so replacing the Ollama container does not require downloading large model files again. |

## Image and Build-Context Sizes

Measurements below were taken with Docker Engine 29.8.0 on Linux/amd64 using the checked-in Dockerfiles. Docker's reported image sizes are uncompressed layer sizes and can differ from registry transfer size.

| Frontend stage | Measured image size | Contents |
|---|---:|---|
| `builder` (`node:22-alpine`) | 618,274,175 bytes (618.3 MB) | Node, `node_modules`, source, and Vite output; used only to compile assets and in the development Compose service. |
| `runtime` (`nginx:1.27-alpine`) | 73,896,717 bytes (73.9 MB) | Nginx runtime, configuration, and static build output; no Node or `node_modules`. |

The requested `<60 MB` runtime target cannot be met while also using the required `nginx:1.27-alpine` base: that base image alone measured 73,574,743 bytes (73.6 MB). The application assets and Nginx configuration add about 0.3 MB. Reducing below 60 MB requires changing the mandated runtime base image (for example, to a smaller compatible Nginx distribution) or changing the runtime server; this build does not misrepresent the measured size.

The frontend directory measured 199,743,002 bytes (199.7 MB) before Docker exclusions. The initial BuildKit build transferred 234.23 kB after applying `frontend/.dockerignore`, a reduction of about 99.88%. The backend directory measured 145,177,782 bytes (145.2 MB); the Docker build transferred 322.34 kB after applying `backend/.dockerignore`, a reduction of about 99.78%. The frontend ignore file omits `node_modules`, `dist`, VCS data, local environment files, and caches. The backend ignore file removes local virtual environments, tests, coverage output, docs, and scripts; the runtime stage copies only application and migration files.

Re-measure after changing dependencies or assets with:

```sh
docker build --target builder -t civicpulse-frontend-builder ./frontend
docker build -t civicpulse-frontend ./frontend
docker image inspect civicpulse-frontend-builder civicpulse-frontend --format '{{.RepoTags}} {{.Size}}'
du -sb frontend
```

## Network Segmentation

```text
Browser -> published frontend -> edge bridge -> backend
                                             backend -> internal bridge -> database
                                                                       -> cache
                                                                       -> ollama
```

`frontend` joins only `edge`. The backend joins both `edge` and `internal` to accept proxied API traffic while reaching data services. PostgreSQL, Redis, and Ollama join only the `internal` network. The internal bridge is marked `internal: true`; production does not publish database or cache ports. The dev Compose file publishes those ports only for local developer tooling.

Validate the resolved network assignments and isolation with:

```sh
docker compose -f compose.yaml config
docker compose --env-file .env -f compose.prod.yaml config
docker compose -f compose.yaml up -d --build
docker compose -f compose.yaml exec frontend ping -c 1 database
```

The final command is expected to fail because `frontend` and `database` do not share a network. Confirm the allowed path from the backend with `docker compose -f compose.yaml exec backend python -c "import socket; print(socket.gethostbyname('database'))"`. Stop the dev stack with `docker compose -f compose.yaml down`; named volumes remain. Add `-v` only when intentionally deleting persisted data.

## Base Image Digest

The requested Python digest `sha256:d1d36d2e05b5f62df9d945f3c1e2b4cb15d6bc39a16a4f9e31d4d380f5530188` is not published for `python:3.12-slim` (Docker Hub returned `manifest unknown`). The backend Dockerfile pins the currently published multi-platform index digest `sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f`, verified against the official registry on 2026-09-28.