"""
Web router — Jinja2 template rendering endpoints.

All routes under ``/web`` are registered here.
Uses Tailwind CSS + HTMX on the frontend.
"""

import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import markdown
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.bookmarks import Bookmark
from src.models.expenses import Account, AccountType, Transaction
from src.models.notes import Note
from src.models.tasks import Task, TaskPriority, TaskStatus
from src.schemas.tasks import ActionItem
from src.services.ledger import process_transaction
from src.services.notes_engine import process_wiki_links
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


# ═══════════════════════════════════════════════════════════════════════════
#  Expenses
# ═══════════════════════════════════════════════════════════════════════════

def _compute_monthly_spending_web(
    db: Session, month_start: datetime, month_end: datetime
) -> tuple[Decimal, dict[str, Decimal]]:
    """
    Compute total spending and category breakdown for a date range.

    Same logic as the API: spending = outflows from non-System accounts
    where to_account_id IS NULL (pure expenses only).
    """
    stmt = select(Transaction).where(
        Transaction.date >= month_start,
        Transaction.date < month_end,
        Transaction.to_account_id.is_(None),
    )
    transactions = list(db.execute(stmt).scalars().all())

    total = Decimal("0.00")
    breakdown: dict[str, Decimal] = {}

    for txn in transactions:
        from_acct = db.get(Account, txn.from_account_id)
        if from_acct is not None and from_acct.type == AccountType.SYSTEM:
            continue

        amount = Decimal(str(txn.amount))
        total += amount
        breakdown[txn.category] = breakdown.get(txn.category, Decimal("0.00")) + amount

    return total, breakdown


@router.get("/expenses", response_class=HTMLResponse)
async def expenses_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Render the expenses dashboard page.

    Computes financial metrics, fetches accounts (for form dropdowns),
    and recent transactions.
    """
    now = datetime.now(timezone.utc)

    # ── Compute metrics ──────────────────────────────────────────────
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month_start = current_month_start + relativedelta(months=1)
    prev_month_start = current_month_start - relativedelta(months=1)

    monthly_spending, category_breakdown = _compute_monthly_spending_web(
        db, current_month_start, next_month_start
    )
    prev_spending, _ = _compute_monthly_spending_web(
        db, prev_month_start, current_month_start
    )

    if prev_spending == Decimal("0.00"):
        mom_pct = 0.0 if monthly_spending == Decimal("0.00") else 100.0
    else:
        mom_pct = float(
            ((monthly_spending - prev_spending) / prev_spending) * 100
        )

    accounts_stmt = select(Account).where(
        Account.type.in_([AccountType.BANK, AccountType.CASH])
    )
    net_worth_accounts = list(db.execute(accounts_stmt).scalars().all())
    net_worth = sum(
        (Decimal(str(a.current_balance)) for a in net_worth_accounts),
        Decimal("0.00"),
    )

    metrics = {
        "net_worth": net_worth,
        "monthly_spending": monthly_spending,
        "mom_spending_change_pct": round(mom_pct, 2),
        "category_breakdown": category_breakdown,
    }

    # Serialize breakdown for Chart.js (Decimal → float)
    breakdown_json = json.dumps(
        {k: float(v) for k, v in category_breakdown.items()}
    )

    # ── Fetch accounts (all types, for form dropdowns) ───────────────
    all_accounts = list(
        db.execute(select(Account).order_by(Account.id)).scalars().all()
    )

    # ── Fetch recent transactions ────────────────────────────────────
    txn_stmt = select(Transaction).order_by(Transaction.id.desc()).limit(50)
    recent_txns = list(db.execute(txn_stmt).scalars().all())

    return templates.TemplateResponse(
        request,
        name="expenses.html",
        context={
            "metrics": metrics,
            "category_breakdown_json": breakdown_json,
            "accounts": all_accounts,
            "transactions": recent_txns,
        },
    )


@router.post("/expenses/hx/transaction", response_class=HTMLResponse)
async def create_transaction_hx(
    request: Request,
    amount: str = Form(...),
    category: str = Form(...),
    description: str = Form(...),
    from_account_id: int = Form(...),
    date: str = Form(""),
    to_account_id: str = Form(""),
    db: Session = Depends(get_db),
):
    """
    HTMX endpoint — create a transaction and return the rendered
    table row partial for injection into the ledger.
    """
    # Parse date
    txn_date = datetime.now(timezone.utc)
    if date:
        txn_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    # Parse optional to_account_id
    to_acct_id: int | None = None
    if to_account_id and to_account_id.strip():
        to_acct_id = int(to_account_id)

    txn = Transaction(
        amount=Decimal(amount),
        date=txn_date,
        description=description,
        category=category,
        from_account_id=from_account_id,
        to_account_id=to_acct_id,
    )
    db.add(txn)
    db.flush()
    db.refresh(txn)

    # Apply balance changes
    process_transaction(db, txn)

    db.commit()
    db.refresh(txn)

    return templates.TemplateResponse(
        request,
        name="partials/transaction_row.html",
        context={"txn": txn},
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Knowledge Base (Notes)
# ═══════════════════════════════════════════════════════════════════════════

def _render_markdown(content: str) -> str:
    """
    Convert note content to HTML.

    Transforms ``[[Title]]`` wiki-links into clickable HTMX links
    before passing through the Markdown processor.
    """
    # Replace [[Title]] with clickable links
    def wiki_to_link(match: re.Match) -> str:
        title = match.group(1).strip()
        return (
            f'<a href="#" class="text-accent-400 hover:underline" '
            f'hx-get="/web/notes/by-title/{title}" '
            f'hx-target="#editor-panel" hx-swap="innerHTML">'
            f'🔗 {title}</a>'
        )

    processed = re.sub(r"\[\[([^\[\]]+)\]\]", wiki_to_link, content)
    return markdown.markdown(processed, extensions=["fenced_code", "tables"])


@router.get("/notes", response_class=HTMLResponse)
async def notes_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the Knowledge Base workspace."""
    stmt = select(Note).order_by(Note.updated_at.desc())
    notes = list(db.execute(stmt).scalars().all())

    return templates.TemplateResponse(
        request,
        name="notes.html",
        context={"notes": notes},
    )

@router.get("/notes/by-title/{title}", response_class=HTMLResponse)
async def get_note_by_title(
    request: Request,
    title: str,
    db: Session = Depends(get_db),
):
    """HTMX endpoint — load a note by title (used by wiki-link clicks)."""
    stmt = select(Note).where(Note.title == title)
    note = db.execute(stmt).scalar_one_or_none()
    if note is None:
        return HTMLResponse(
            f'<p class="text-sm text-slate-400 py-4">Note "{title}" not found.</p>',
            status_code=404,
        )

    rendered_html = _render_markdown(note.content) if note.content else ""

    return templates.TemplateResponse(
        request,
        name="partials/note_editor.html",
        context={"note": note, "rendered_html": rendered_html},
    )


@router.get("/notes/{note_id}", response_class=HTMLResponse)
async def get_note_editor(
    request: Request,
    note_id: int,
    db: Session = Depends(get_db),
):
    """HTMX endpoint — load a note into the editor panel with Markdown preview."""
    note = db.get(Note, note_id)
    if note is None:
        return HTMLResponse(
            '<p class="text-sm text-rose-400 py-4">Note not found.</p>',
            status_code=404,
        )

    rendered_html = _render_markdown(note.content) if note.content else ""

    return templates.TemplateResponse(
        request,
        name="partials/note_editor.html",
        context={"note": note, "rendered_html": rendered_html},
    )


@router.post("/notes/hx/create", response_class=HTMLResponse)
async def create_note_hx(
    request: Request,
    title: str = Form(...),
    content: str = Form(""),
    db: Session = Depends(get_db),
):
    """
    HTMX endpoint — create a note and return the sidebar list item
    partial for injection. Also processes wiki-links.
    """
    note = Note(title=title, content=content)
    db.add(note)
    db.flush()

    process_wiki_links(db, note)

    db.commit()
    db.refresh(note)

    return templates.TemplateResponse(
        request,
        name="partials/note_item.html",
        context={"note": note},
    )


@router.post("/notes/hx/save", response_class=HTMLResponse)
async def save_note_hx(
    note_id: int = Form(...),
    title: str = Form(...),
    content: str = Form(""),
    db: Session = Depends(get_db),
):
    """
    HTMX endpoint — update a note's title and content,
    re-process wiki-links, and return a success feedback fragment.
    """
    note = db.get(Note, note_id)
    if note is None:
        return HTMLResponse(
            '<span class="text-rose-400">Note not found</span>',
            status_code=404,
        )

    note.title = title
    note.content = content
    db.flush()

    process_wiki_links(db, note)

    db.commit()

    return HTMLResponse(
        '<span class="text-emerald-400 font-medium">'
        '✓ Saved</span>'
    )
