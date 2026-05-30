"""
API v1 router — JSON response endpoints.

All routes under ``/api/v1`` are registered here.
Sub-module routers are included below.
"""

from fastapi import APIRouter

from src.api.v1.bookmarks import router as bookmarks_router
from src.api.v1.expenses import router as expenses_router
from src.api.v1.notes import router as notes_router
from src.api.v1.tasks import router as tasks_router

router = APIRouter(prefix="/api/v1", tags=["api-v1"])

# ── Sub-module routers ──────────────────────────────────────────────────────
router.include_router(bookmarks_router)
router.include_router(tasks_router)
router.include_router(expenses_router)
router.include_router(notes_router)


@router.get("/health")
async def health_check() -> dict:
    """Lightweight liveness probe for the API layer."""
    return {"status": "healthy", "layer": "api", "version": "v1"}

