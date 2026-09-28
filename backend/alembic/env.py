"""
alembic/env.py
──────────────
Alembic migration environment.

Key design points:
  1. Reads DATABASE_SYNC_URL from .env (via python-dotenv) so the DSN is
     never hard-coded in alembic.ini.
  2. Imports all ORM models via `app.models` to populate Base.metadata so
     that `alembic revision --autogenerate` detects all tables automatically.
  3. Supports both offline mode (generates SQL script) and online mode
     (runs migrations against a live DB).
  4. NEVER calls Base.metadata.create_all() — only Alembic DDL operations.
"""
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Load environment variables from .env ──────────────────────────────────────
load_dotenv()

# ── Alembic Config object ─────────────────────────────────────────────────────
config = context.config

# Override the sqlalchemy.url from the environment (sync psycopg2 DSN)
database_sync_url = os.environ.get("DATABASE_SYNC_URL")
if database_sync_url:
    config.set_main_option("sqlalchemy.url", database_sync_url)

# Configure Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import all models so Base.metadata is fully populated ─────────────────────
# This import MUST happen before `target_metadata` is assigned.
from app.core.database import Base  # noqa: E402
import app.models  # noqa: E402, F401 – side effect: registers all ORM models

target_metadata = Base.metadata


# ── Offline migration (generates SQL script, no DB connection needed) ─────────
def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates a SQL script that can be reviewed and applied manually.
    Useful for environments where direct DB access from the migration runner
    is restricted (e.g., production with a DBA approval gate).
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Render PostgreSQL-native enum types in generated SQL
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migration (runs DDL against a live PostgreSQL instance) ────────────
def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode against a live database connection.

    Uses NullPool to avoid connection pool overhead in a short-lived
    migration process (Alembic runs once and exits).
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Render server defaults in migration output for accuracy
            render_as_batch=False,
            # Compare column types strictly (catches enum changes)
            compare_type=True,
            # Compare server defaults (e.g., status default 'open')
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
