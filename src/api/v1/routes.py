"""
API v1 router — JSON response endpoints.

All routes under ``/api/v1`` are registered here.
CRUD routes will be added to this router in future modules.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["api-v1"])


@router.get("/health")
async def health_check() -> dict:
    """Lightweight liveness probe for the API layer."""
    return {"status": "healthy", "layer": "api", "version": "v1"}
