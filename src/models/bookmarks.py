"""
Bookmarks module — SQLAlchemy models.

Defines Bookmark, Tag, and the Many-to-Many association table between them.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

# ── Many-to-Many association table ──────────────────────────────────────────
bookmark_tag = Table(
    "bookmark_tag",
    Base.metadata,
    Column("bookmark_id", Integer, ForeignKey("bookmarks.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


class Bookmark(Base):
    """A saved URL with optional metadata and tags."""

    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    tags: Mapped[list["Tag"]] = relationship(
        secondary=bookmark_tag, back_populates="bookmarks", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Bookmark(id={self.id}, url='{self.url}')>"


class Tag(Base):
    """A label that can be attached to one or more bookmarks."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # Relationships
    bookmarks: Mapped[list["Bookmark"]] = relationship(
        secondary=bookmark_tag, back_populates="tags", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, name='{self.name}')>"
