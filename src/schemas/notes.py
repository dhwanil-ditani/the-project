"""
Pydantic schemas for the Personal Knowledge Base module.

Covers Note CRUD and graph visualization (nodes + edges).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ── Note CRUD schemas ───────────────────────────────────────────────────────
class NoteCreate(BaseModel):
    """Payload for creating a new note."""

    title: str
    content: str = ""


class NoteUpdate(BaseModel):
    """Payload for updating an existing note. All fields optional."""

    title: str | None = None
    content: str | None = None


class NoteResponse(BaseModel):
    """Full note representation returned by the API."""

    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Graph visualization schemas ────────────────────────────────────────────
class GraphNode(BaseModel):
    """A node in the knowledge graph."""

    id: int
    label: str  # maps to Note.title


class GraphEdge(BaseModel):
    """A directed edge in the knowledge graph."""

    from_id: int
    to_id: int


class GraphPayload(BaseModel):
    """Complete graph structure for visualization."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
