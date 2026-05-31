"""
Web router — Jinja2 template rendering endpoints.

All routes under ``/web`` are registered here.
Uses Tailwind CSS + HTMX on the frontend.
"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.bookmarks import Bookmark
from src.models.tasks import Task, TaskPriority, TaskStatus
from src.schemas.tasks import ActionItem
from src.services.scraper import scrape_url_metadata
from src.services.task_engine import evaluate_pending_tasks

router = APIRouter(prefix="/web", tags=["web"])

# ── Template setup ──────────────────────────────────────────────────────────
_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

# Priority sort order (High → Low)
_PRIORITY_ORDER = {
    TaskPriority.HIGH: 0,
    TaskPriority.MEDIUM: 1,
    TaskPriority.LOW: 2,
}


# ── Health check ────────────────────────────────────────────────────────────
@router.get("/health")
async def web_health() -> dict:
    """Liveness probe for the web/template layer."""
    return {"status": "healthy", "layer": "web"}


# ═══════════════════════════════════════════════════════════════════════════
#  Dashboard
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Unified dashboard view.

    Triggers lazy evaluation, then renders all pending/overdue tasks
    sorted by priority and due date.
    """
    # Run the lazy evaluation engine
    evaluate_pending_tasks(db)
    db.commit()

    now = datetime.now(timezone.utc)

    # Pending tasks due today or earlier
    stmt = select(Task).where(
        Task.status == TaskStatus.PENDING,
        Task.due_date.isnot(None),
        Task.due_date <= now,
    )
    tasks: list[Task] = list(db.execute(stmt).scalars().all())

    # Also include undated pending tasks
    undated_stmt = select(Task).where(
        Task.status == TaskStatus.PENDING,
        Task.due_date.is_(None),
    )
    tasks.extend(db.execute(undated_stmt).scalars().all())

    # Sort: priority (High → Low), then due_date (earliest first, None last)
    def sort_key(t: Task):
        prio = _PRIORITY_ORDER.get(t.priority, 99)
        due = t.due_date if t.due_date is not None else datetime.max.replace(tzinfo=timezone.utc)
        return (prio, due)

    tasks.sort(key=sort_key)

    # Map to ActionItem
    action_items: list[ActionItem] = []
    for task in tasks:
        is_habit = False
        if task.rule is not None:
            is_habit = not task.rule.is_strict

        action_items.append(
            ActionItem(
                id=task.id,
                title=task.title,
                description=task.description,
                priority=task.priority.value,
                status=task.status.value,
                due_date=task.due_date,
                project_tag=task.project_tag,
                rule_id=task.rule_id,
                is_habit=is_habit,
            )
        )

    today_date = now.strftime("%A, %B %d, %Y")

    return templates.TemplateResponse(
        request,
        name="dashboard.html",
        context={
            "action_items": action_items,
            "today_date": today_date,
        },
    )


# ── HTMX: Complete a task ──────────────────────────────────────────────────
@router.patch("/tasks/{task_id}/complete", response_class=HTMLResponse)
async def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
):
    """
    HTMX endpoint — marks a task as Completed and returns a
    replacement HTML fragment (the row fades out / shows completed).
    """
    task = db.get(Task, task_id)
    if task is None:
        return HTMLResponse(
            '<div class="text-xs text-rose-400 px-5 py-2">Task not found</div>',
            status_code=404,
        )

    task.status = TaskStatus.COMPLETED
    db.commit()

    # Return a completion confirmation fragment
    return HTMLResponse(f"""
    <div id="task-row-{task_id}"
         class="flex items-center gap-4 bg-surface-800/50 border border-emerald-500/20 rounded-xl px-5 py-4 transition-all duration-300">
      <div class="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-500/20 border-2 border-emerald-500 flex items-center justify-center">
        <svg class="w-3.5 h-3.5 text-emerald-400" fill="currentColor" viewBox="0 0 24 24">
          <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
        </svg>
      </div>
      <div class="flex-1">
        <p class="text-sm font-medium text-slate-500 line-through">{task.title}</p>
        <p class="text-[10px] text-emerald-500 font-medium mt-0.5">Completed</p>
      </div>
    </div>
    """)


# ═══════════════════════════════════════════════════════════════════════════
#  Bookmarks
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/bookmarks", response_class=HTMLResponse)
async def bookmarks_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the bookmarks page with all saved bookmarks."""
    stmt = select(Bookmark).order_by(Bookmark.id.desc())
    bookmarks = list(db.execute(stmt).scalars().all())

    return templates.TemplateResponse(
        request,
        name="bookmarks.html",
        context={"bookmarks": bookmarks},
    )


@router.post("/bookmarks/hx", response_class=HTMLResponse)
async def create_bookmark_hx(
    request: Request,
    url: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    HTMX endpoint — create a bookmark from a URL and return the
    rendered card partial for injection into the grid.

    Auto-scrapes title, description, and favicon when missing.
    """
    # Auto-scrape metadata
    metadata = await scrape_url_metadata(url)

    bookmark = Bookmark(
        url=url,
        title=metadata.title,
        description=metadata.description,
        favicon_url=metadata.favicon_url,
    )
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)

    return templates.TemplateResponse(
        request,
        name="partials/bookmark_card.html",
        context={"bookmark": bookmark},
    )


@router.delete("/bookmarks/hx/{bookmark_id}", response_class=HTMLResponse)
async def delete_bookmark_hx(
    bookmark_id: int,
    db: Session = Depends(get_db),
):
    """
    HTMX endpoint — delete a bookmark and return empty response
    so HTMX removes the element from the DOM.
    """
    bookmark = db.get(Bookmark, bookmark_id)
    if bookmark is None:
        return HTMLResponse("", status_code=404)

    db.delete(bookmark)
    db.commit()

    # Return empty string — HTMX outerHTML swap removes the card
    return HTMLResponse("")

