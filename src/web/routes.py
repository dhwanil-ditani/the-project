"""
Web router — Jinja2 template rendering endpoints.

All routes under ``/web`` are registered here.
Template-rendered pages will be added to this router in future modules.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/web", tags=["web"])


@router.get("/health")
async def web_health() -> dict:
    """Liveness probe for the web/template layer."""
    return {"status": "healthy", "layer": "web"}
