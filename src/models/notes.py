"""
Personal Knowledge Base — SQLAlchemy models.

Defines Note (with unique title) and NoteLink for bidirectional
wiki-link connections between notes.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class NoteLink(Base):
    """
    Directed edge between two notes, representing a ``[[wiki-link]]``.

    source_note → target_note.
    """

    __tablename__ = "note_links"

    source_note_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True
    )
    target_note_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True
    )


class Note(Base):
    """A knowledge-base note with wiki-link support."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Outgoing links: notes this note links TO
    outgoing_links: Mapped[list["Note"]] = relationship(
        "Note",
        secondary="note_links",
        primaryjoin="Note.id == NoteLink.source_note_id",
        secondaryjoin="Note.id == NoteLink.target_note_id",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Note(id={self.id}, title='{self.title}')>"
