"""
app/core/database.py
────────────────────
Async SQLAlchemy engine + session factory.

Design decisions:
  • Uses asyncpg driver (postgresql+asyncpg) for non-blocking I/O.
  • Session is scoped per HTTP request via FastAPI dependency injection
    (see get_session dependency below).
  • NEVER calls metadata.create_all() – table creation is exclusively
    managed by Alembic migrations (guardrail enforced by project policy).
  • pool_pre_ping=True detects stale connections automatically so the app
    survives a DB restart without manual intervention.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,          # logs SQL only in debug mode
    pool_pre_ping=True,               # validates connection health before use
    pool_size=10,                     # sensible default for a single-instance app
    max_overflow=20,                  # burst headroom above pool_size
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,           # avoids lazy-load errors after commit
    autoflush=False,                  # explicit flush = predictable behaviour
    autocommit=False,
)


async def check_database_health() -> bool:
    """Return whether PostgreSQL can execute a lightweight query."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


# ── Declarative base (shared by all ORM models) ───────────────────────────────
class Base(DeclarativeBase):
    """All SQLAlchemy ORM models must inherit from this class."""
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an AsyncSession scoped to the current HTTP request.

    Usage in a route::

        @router.get("/")
        async def handler(db: AsyncSession = Depends(get_session)):
            ...

    The session is committed on success and rolled back on any exception,
    then always closed via the async-context-manager.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
