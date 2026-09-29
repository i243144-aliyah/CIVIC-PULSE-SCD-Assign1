"""
app/routes/__init__.py
"""

from app.routes.complaints import router as complaints_router
from app.routes.health import router as health_router
from app.routes.meta import router as meta_router

__all__ = ["complaints_router", "health_router", "meta_router"]
