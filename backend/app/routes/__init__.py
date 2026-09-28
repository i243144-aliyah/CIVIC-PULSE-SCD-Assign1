"""
app/routes/__init__.py
"""

from app.routes.complaints import router as complaints_router  # noqa: F401
from app.routes.health import router as health_router  # noqa: F401

__all__ = ["complaints_router", "health_router"]
