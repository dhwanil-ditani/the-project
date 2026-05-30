"""
Personal OS — Application entry point.

This module wires together the dual-router pattern:
  • ``/api/v1/``  → JSON API responses
  • ``/web/``     → Jinja2 template rendering

No route logic lives here; it is strictly a composition root.
"""

from fastapi import FastAPI

from src.api.v1.routes import router as api_v1_router
from src.web.routes import router as web_router

app = FastAPI(
    title="Personal OS",
    description="A modular personal operating system backend.",
    version="0.1.0",
)

# ── Mount routers ───────────────────────────────────────────────────────────
app.include_router(api_v1_router)
app.include_router(web_router)


# ── Root health check ──────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def root_health() -> dict:
    """Top-level liveness probe."""
    return {
        "status": "healthy",
        "app": "personal-os",
        "version": "0.1.0",
    }
