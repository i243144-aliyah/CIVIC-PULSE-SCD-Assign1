"""
app/models/__init__.py
──────────────────────
Re-exports all ORM models so that Alembic's `env.py` can import them via::

    from app.models import *

This ensures Base.metadata knows about every table when generating migrations.
"""

from app.models.complaint import Complaint  # noqa: F401

__all__ = ["Complaint"]
