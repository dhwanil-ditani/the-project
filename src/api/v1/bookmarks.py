"""
Bookmarks API — CRUD endpoints.

Mounted at ``/api/v1/bookmarks`` via the v1 router.
On POST, if title or description are absent, the scraper service is
called automatically to fill them in before persisting.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.bookmarks import Bookmark, Tag
from src.schemas.bookmarks import BookmarkCreate, BookmarkResponse, BookmarkUpdate
from src.services.scraper import scrape_url_metadata

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


# ── Helpers ─────────────────────────────────────────────────────────────────
def _get_or_create_tags(db: Session, tag_names: list[str]) -> list[Tag]:
    """Resolve tag names to Tag ORM instances, creating any that don't exist."""
    tags: list[Tag] = []
    for name in tag_names:
        name = name.strip().lower()
        if not name:
            continue
        tag = db.execute(select(Tag).where(Tag.name == name)).scalar_one_or_none()
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()  # assign ID without committing
        tags.append(tag)
    return tags


def _get_bookmark_or_404(db: Session, bookmark_id: int) -> Bookmark:
    """Fetch a bookmark by ID or raise 404."""
    bookmark = db.get(Bookmark, bookmark_id)
    if bookmark is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bookmark with id {bookmark_id} not found",
        )
    return bookmark


# ── POST /bookmarks ────────────────────────────────────────────────────────
@router.post("/", response_model=BookmarkResponse, status_code=status.HTTP_201_CREATED)
async def create_bookmark(
    payload: BookmarkCreate,
    db: Session = Depends(get_db),
) -> Bookmark:
    """
    Create a new bookmark.

    If ``title`` or ``description`` are not provided, the URL is scraped
    automatically to fill in the missing metadata.
    """
    url_str = str(payload.url)

    # Auto-scrape when metadata is missing
    if payload.title is None or payload.description is None:
        metadata = await scrape_url_metadata(url_str)
        if payload.title is None and metadata.title:
            payload.title = metadata.title
        if payload.description is None and metadata.description:
            payload.description = metadata.description
        if payload.favicon_url is None and metadata.favicon_url:
            payload.favicon_url = metadata.favicon_url

    bookmark = Bookmark(
        url=url_str,
        title=payload.title,
        description=payload.description,
        favicon_url=payload.favicon_url,
    )

    # Resolve tags
    if payload.tags:
        bookmark.tags = _get_or_create_tags(db, payload.tags)

    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return bookmark


# ── GET /bookmarks ──────────────────────────────────────────────────────────
@router.get("/", response_model=list[BookmarkResponse])
async def list_bookmarks(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[Bookmark]:
    """Return a paginated list of all bookmarks."""
    stmt = select(Bookmark).offset(skip).limit(limit).order_by(Bookmark.id.desc())
    return list(db.execute(stmt).scalars().all())


# ── GET /bookmarks/{id} ────────────────────────────────────────────────────
@router.get("/{bookmark_id}", response_model=BookmarkResponse)
async def get_bookmark(
    bookmark_id: int,
    db: Session = Depends(get_db),
) -> Bookmark:
    """Retrieve a single bookmark by ID."""
    return _get_bookmark_or_404(db, bookmark_id)


# ── PUT /bookmarks/{id} ────────────────────────────────────────────────────
@router.put("/{bookmark_id}", response_model=BookmarkResponse)
async def update_bookmark(
    bookmark_id: int,
    payload: BookmarkUpdate,
    db: Session = Depends(get_db),
) -> Bookmark:
    """Update an existing bookmark. Only provided fields are changed."""
    bookmark = _get_bookmark_or_404(db, bookmark_id)

    update_data = payload.model_dump(exclude_unset=True)

    # Handle tags separately
    tag_names = update_data.pop("tags", None)
    if tag_names is not None:
        bookmark.tags = _get_or_create_tags(db, tag_names)

    for field, value in update_data.items():
        if field == "url" and value is not None:
            value = str(value)
        setattr(bookmark, field, value)

    db.commit()
    db.refresh(bookmark)
    return bookmark


# ── DELETE /bookmarks/{id} ──────────────────────────────────────────────────
@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark(
    bookmark_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a bookmark by ID."""
    bookmark = _get_bookmark_or_404(db, bookmark_id)
    db.delete(bookmark)
    db.commit()
