"""
Pydantic schemas for the Bookmarks module.

Defines request/response models for bookmark CRUD operations.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


# ── Nested schemas ──────────────────────────────────────────────────────────
class TagSchema(BaseModel):
    """Read-only representation of a Tag."""

    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


# ── Request schemas ─────────────────────────────────────────────────────────
class BookmarkCreate(BaseModel):
    """Payload for creating a new bookmark."""

    url: HttpUrl
    title: str | None = None
    description: str | None = None
    favicon_url: str | None = None
    tags: list[str] = []


class BookmarkUpdate(BaseModel):
    """Payload for updating an existing bookmark. All fields optional."""

    url: HttpUrl | None = None
    title: str | None = None
    description: str | None = None
    favicon_url: str | None = None
    tags: list[str] | None = None


# ── Response schemas ────────────────────────────────────────────────────────
class BookmarkResponse(BaseModel):
    """Full bookmark representation returned by the API."""

    id: int
    url: str
    title: str | None
    description: str | None
    favicon_url: str | None
    created_at: datetime
    tags: list[TagSchema] = []

    model_config = ConfigDict(from_attributes=True)
