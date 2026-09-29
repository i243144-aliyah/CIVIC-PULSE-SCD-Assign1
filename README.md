
# CivicPulse API

AI-assisted civic complaint management system built with FastAPI, Pydantic v2, SQLAlchemy (async), and PostgreSQL 16.

---

## Architecture: Strict Four-Layer Separation

```
HTTP Request
    │
    ▼
┌──────────────────────────────────────────────┐
│  app/routes/          HTTP layer              │  Parse input → call service → serialize output
│  (complaints.py, health.py)                  │  NO business logic, NO direct DB access
└──────────────────────────────┬───────────────┘
                               │ Pydantic schemas
                               ▼
┌──────────────────────────────────────────────┐
│  app/services/        Business logic layer   │  State machine, triage orchestration,
│  (triage_service.py)                         │  fallback chain, domain exceptions
└──────────────────────┬───────────────────────┘
              ┌────────┴──────────┐
              │ Pydantic/dicts    │ TriageResult
              ▼                   ▼
┌─────────────────────┐  ┌───────────────────────────┐
│  app/repositories/  │  │  app/providers/            │
│  (complaint_repo)   │  │  (groq, ollama, rules)     │
│  ALL SQL here       │  │  ALL outbound HTTP here    │
│  NO business logic  │  │  NO business logic         │
└─────────────────────┘  └───────────────────────────┘
         │
         ▼
  PostgreSQL 16
```

---

## Quick Start

### 1. Clone and set up the environment

```bash
# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your database credentials
```

### 3. Start PostgreSQL 16

```bash
docker compose up -d db
# Wait for the health check to pass
docker compose ps
```

### 4. Run database migrations

```bash
# Apply all migrations (creates tables, enums, indexes)
alembic upgrade head

# Never run: Base.metadata.create_all() — Alembic owns all DDL
```

### 5. Seed the database

```bash
# Load 30 realistic complaints (idempotent — safe to run multiple times)
python scripts/seed.py
```

### 6. Start the API server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

---

## Directory Structure

```
civicpulse-SCD-1/
├── app/
│   ├── core/
│   │   ├── config.py        # Pydantic-settings: all env vars
│   │   ├── database.py      # Async SQLAlchemy engine + DI session
│   │   └── enums.py         # Single source of truth for all enums
│   ├── models/
│   │   └── complaint.py     # SQLAlchemy ORM model (schema only, no logic)
│   ├── schemas/
│   │   └── complaint.py     # Pydantic v2 request/response schemas
│   ├── repositories/
│   │   └── complaint_repository.py   # ALL SQL lives here
│   ├── services/
│   │   └── triage_service.py         # Business logic + state machine
│   ├── providers/
│   │   ├── base.py           # TriageProvider Protocol + TriageResult
│   │   ├── groq_provider.py  # Groq LLM integration
│   │   ├── ollama_provider.py # Ollama local LLM integration
│   │   └── rules_provider.py # Deterministic keyword rules engine
│   └── main.py              # FastAPI application factory
├── alembic/
│   ├── versions/
│   │   └── 0001_initial_complaints_schema.py  ← THE migration
│   ├── env.py               # Alembic environment (reads DATABASE_SYNC_URL)
│   └── script.py.mako       # Migration file template
├── scripts/
│   └── seed.py              # Idempotent 30-complaint seed
├── alembic.ini
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## Database Schema

### `complaints` table

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK, `gen_random_uuid()` server default |
| `text` | `VARCHAR(2000)` | NOT NULL, CHECK 10–2000 chars |
| `location` | `VARCHAR(200)` | NOT NULL, CHECK 3–200 chars |
| `reporter_contact` | `VARCHAR(255)` | nullable |
| `category` | `ENUM` | water, electricity, sanitation, roads, streetlights, other |
| `priority` | `ENUM` | high, normal, low |
| `status` | `ENUM` | open (default), in_progress, resolved, rejected |
| `ai_summary` | `VARCHAR(140)` | nullable, CHECK ≤140 chars |
| `triaged_by` | `ENUM` | llm:groq, llm:ollama, rules, rules:fallback |
| `triage_latency_ms` | `INTEGER` | NOT NULL, CHECK ≥0 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, `now()` server default |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, `now()` server default |

### Indexes

| Index | Columns | Serves |
|---|---|---|
| `ix_complaints_status_priority` | `(status, priority)` | Admin list: `WHERE status='open' ORDER BY priority` |
| `ix_complaints_created_at` | `(created_at)` | Chronological feed, cursor pagination, date-range reports |

---

## Provider Fallback Chain

```
POST /api/v1/complaints
        │
        ▼
  GroqProvider.is_available()?
        ├── YES → triage() → success? → persist
        │                  └── fail  → try Ollama
        └── NO  → try Ollama
                      │
                      ▼
              OllamaProvider.is_available()?
                      ├── YES → triage() → success? → persist (triaged_by=llm:ollama)
                      │                  └── fail  → rules fallback
                      └── NO  → RulesProvider (triaged_by=rules or rules:fallback)
```

---

## Status State Machine

```
open ──→ in_progress ──→ resolved
  │              │
  └──→ rejected ←┘
```

Terminal states: `resolved`, `rejected` (no further transitions allowed).

---

## Alembic Commands

```bash
# Apply all pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1

# Roll back to clean slate
alembic downgrade base

# Auto-generate a new migration (after changing ORM models)
alembic revision --autogenerate -m "describe your change"

# Show current revision
alembic current

# Show migration history
alembic history --verbose
```

---

## Seed Script

```bash
# Run once (inserts 30 complaints)
python scripts/seed.py

# Run again (skips all 30 — idempotent)
python scripts/seed.py

# Output:
# [seed] Done. Inserted: 30, Skipped (already existed): 0, Total seed rows: 30
# [seed] Done. Inserted: 0,  Skipped (already existed): 30, Total seed rows: 30
```

Idempotency is achieved via deterministic `uuid5` IDs derived from seed row index.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/complaints` | Submit new complaint (triggers triage) |
| `GET` | `/api/v1/complaints` | List complaints (filter by status/category/priority) |
| `GET` | `/api/v1/complaints/{id}` | Get single complaint |
| `PATCH` | `/api/v1/complaints/{id}/status` | Transition complaint status |
| `GET` | `/health/live` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe (checks DB) |

## Frontend

Start the API on port 8000, then run the React development UI from the project root:

```bash
cd frontend
npm install
npm run dev
```

Vite proxies relative `/api` requests to `http://localhost:8000`, so the built client does not bake in an environment-specific API URL. Run component tests with `npm test` and create a production bundle with `npm run build`.
>>>>>>> dev
