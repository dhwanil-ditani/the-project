"""
Notes API — CRUD endpoints and Knowledge Graph.

Mounted at ``/api/v1/notes`` via the v1 router.
On POST and PUT, wiki-links in content are processed to maintain
the bidirectional graph edges.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.notes import Note, NoteLink
from src.schemas.notes import (
    GraphEdge,
    GraphNode,
    GraphPayload,
    NoteCreate,
    NoteResponse,
    NoteUpdate,
)
from src.services.notes_engine import process_wiki_links

router = APIRouter(prefix="/notes", tags=["notes"])


# ── Helpers ─────────────────────────────────────────────────────────────────
def _get_note_or_404(db: Session, note_id: int) -> Note:
    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note with id {note_id} not found",
        )
    return note


# ── POST /notes ─────────────────────────────────────────────────────────────
@router.post("/", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteCreate,
    db: Session = Depends(get_db),
) -> Note:
    """Create a new note and process any [[wiki-links]] in its content."""
    note = Note(title=payload.title, content=payload.content)
    db.add(note)
    db.flush()  # assign ID before processing links

    process_wiki_links(db, note)

    db.commit()
    db.refresh(note)
    return note


# ── GET /notes ──────────────────────────────────────────────────────────────
@router.get("/", response_model=list[NoteResponse])
async def list_notes(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[Note]:
    """Return a paginated list of all notes."""
    stmt = select(Note).offset(skip).limit(limit).order_by(Note.id.desc())
    return list(db.execute(stmt).scalars().all())


# ── GET /notes/graph (MUST be before /{note_id} to avoid path conflict) ────
@router.get("/graph", response_model=GraphPayload)
async def get_graph(
    db: Session = Depends(get_db),
) -> GraphPayload:
    """
    Return the complete knowledge graph as nodes and edges.

    Each note becomes a GraphNode (id + label=title).
    Each NoteLink becomes a GraphEdge (from_id → to_id).
    """
    notes = list(db.execute(select(Note)).scalars().all())
    links = list(db.execute(select(NoteLink)).scalars().all())

    nodes = [GraphNode(id=n.id, label=n.title) for n in notes]
    edges = [
        GraphEdge(from_id=lnk.source_note_id, to_id=lnk.target_note_id)
        for lnk in links
    ]

    return GraphPayload(nodes=nodes, edges=edges)


# ── GET /notes/{id} ────────────────────────────────────────────────────────
@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: int,
    db: Session = Depends(get_db),
) -> Note:
    """Retrieve a single note by ID."""
    return _get_note_or_404(db, note_id)


# ── PUT /notes/{id} ────────────────────────────────────────────────────────
@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: int,
    payload: NoteUpdate,
    db: Session = Depends(get_db),
) -> Note:
    """Update an existing note and re-process [[wiki-links]]."""
    note = _get_note_or_404(db, note_id)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(note, field, value)

    db.flush()
    process_wiki_links(db, note)

    db.commit()
    db.refresh(note)
    return note


# ── DELETE /notes/{id} ──────────────────────────────────────────────────────
@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a note by ID."""
    note = _get_note_or_404(db, note_id)
    db.delete(note)
    db.commit()
