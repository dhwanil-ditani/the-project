"""
Wiki-Link Engine for the Personal Knowledge Base.

Parses ``[[Title]]`` references inside note content, auto-creates
placeholder notes for missing targets, and maintains the NoteLink
edge table.
"""

import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.models.notes import Note, NoteLink

# Matches [[Title]] with any non-bracket content inside
_WIKI_LINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")


def extract_wiki_links(content: str) -> list[str]:
    """
    Extract all ``[[Title]]`` references from note content.

    Returns a deduplicated list of titles (preserving first-seen order).
    """
    seen: set[str] = set()
    titles: list[str] = []
    for match in _WIKI_LINK_RE.finditer(content):
        title = match.group(1).strip()
        if title and title not in seen:
            seen.add(title)
            titles.append(title)
    return titles


def _get_or_create_note(db: Session, title: str) -> Note:
    """
    Find a note by title or create a placeholder with empty content.
    """
    stmt = select(Note).where(Note.title == title)
    note = db.execute(stmt).scalar_one_or_none()
    if note is None:
        note = Note(title=title, content="")
        db.add(note)
        db.flush()  # assign ID
    return note


def process_wiki_links(db: Session, source_note: Note) -> None:
    """
    Synchronise the NoteLink table for a given source note.

    1. Parse all ``[[Title]]`` references from ``source_note.content``.
    2. Auto-create placeholder notes for any missing titles.
    3. Clear existing outgoing links for this source note.
    4. Insert fresh NoteLink rows for each discovered target.
    """
    titles = extract_wiki_links(source_note.content)

    # Resolve target notes (create placeholders as needed)
    target_notes = [_get_or_create_note(db, t) for t in titles]

    # Clear existing outgoing links
    db.execute(
        delete(NoteLink).where(NoteLink.source_note_id == source_note.id)
    )
    db.flush()

    # Insert new links (skip self-links)
    for target in target_notes:
        if target.id != source_note.id:
            link = NoteLink(
                source_note_id=source_note.id,
                target_note_id=target.id,
            )
            db.add(link)

    db.flush()
