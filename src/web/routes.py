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
import uuid
import shutil
import os
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.bookmarks import Bookmark
from src.models.expenses import Account, AccountType, Transaction
from src.models.notes import Note
from src.models.tasks import RecurringRule, Task, TaskPriority, TaskStatus
from src.schemas.tasks import ActionItem
from src.services.ledger import process_transaction
from src.services.notes_engine import process_wiki_links
from src.services.scraper import scrape_url_metadata
from src.services.task_engine import (
    _compute_next_due,
    _spawn_next_task,
    evaluate_pending_tasks,
)

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

    # For cross-module linking: notes dictionary mapping Note ID -> Title
    notes_stmt = select(Note)
    all_notes = list(db.execute(notes_stmt).scalars().all())
    notes_map = {n.id: n.title for n in all_notes}
    task_notes = {t.id: t.note_id for t in tasks if t.note_id is not None}

    return templates.TemplateResponse(
        request,
        name="dashboard.html",
        context={
            "action_items": action_items,
            "today_date": today_date,
            "notes_map": notes_map,
            "task_notes": task_notes,
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
#  Tasks Manager (Backlog & Rules)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/tasks", response_class=HTMLResponse)
async def tasks_manager_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Render the full tasks backlog and recurring rules manager."""
    tasks_stmt = select(Task).order_by(
        Task.status, Task.priority, Task.due_date.desc().nulls_last(), Task.id.desc()
    ).limit(100)
    tasks = list(db.execute(tasks_stmt).scalars().all())

    rules_stmt = select(RecurringRule).order_by(RecurringRule.id.desc())
    rules = list(db.execute(rules_stmt).scalars().all())

    notes_stmt = select(Note).order_by(Note.title)
    all_notes = list(db.execute(notes_stmt).scalars().all())
    notes_map = {n.id: n.title for n in all_notes}

    return templates.TemplateResponse(
        request,
        name="tasks_manager.html",
        context={"tasks": tasks, "rules": rules, "notes": all_notes, "notes_map": notes_map},
    )


@router.post("/tasks/hx/standard", response_class=HTMLResponse)
async def create_standard_task_hx(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    priority: str = Form("Medium"),
    due_date: str = Form(""),
    note_id: str = Form(""),
    db: Session = Depends(get_db),
):
    """HTMX endpoint to create a standalone task and return its table row."""
    dt = None
    if due_date:
        dt = datetime.strptime(due_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    parsed_note_id = int(note_id) if note_id and note_id.strip() else None

    task = Task(
        title=title,
        description=description,
        priority=TaskPriority(priority),
        status=TaskStatus.PENDING,
        due_date=dt,
        note_id=parsed_note_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    notes_stmt = select(Note)
    all_notes = list(db.execute(notes_stmt).scalars().all())
    notes_map = {n.id: n.title for n in all_notes}

    return templates.TemplateResponse(
        request,
        name="partials/task_row.html",
        context={"task": task, "notes_map": notes_map},
    )


@router.post("/tasks/hx/recurring", response_class=HTMLResponse)
async def create_recurring_rule_hx(
    request: Request,
    task_title: str = Form(...),
    rrule_string: str = Form(...),
    is_strict: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """
    HTMX endpoint to create a recurring rule, spawn its initial task,
    and return the rule's table row.
    """
    now = datetime.now(timezone.utc)
    rule = RecurringRule(
        task_title=task_title,
        rrule_string=rrule_string,
        is_strict=bool(is_strict),
    )

    next_due = _compute_next_due(rrule_string, now)
    if next_due is None:
        next_due = now

    rule.next_due = next_due
    db.add(rule)
    db.flush()

    # Spawn the very first task so the rule is picked up by lazy evaluation later
    _spawn_next_task(db, rule, next_due)

    db.commit()
    db.refresh(rule)

    return templates.TemplateResponse(
        request,
        name="partials/rule_row.html",
        context={"rule": rule},
    )


@router.get("/tasks/hx/{task_id}", response_class=HTMLResponse)
async def get_task_hx(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
):
    """HTMX endpoint to return the static task row (used to cancel edit)."""
    task = db.get(Task, task_id)
    if not task:
        return HTMLResponse("<tr><td colspan='6' class='text-rose-400'>Task not found</td></tr>", status_code=404)
    
    notes_stmt = select(Note)
    all_notes = list(db.execute(notes_stmt).scalars().all())
    notes_map = {n.id: n.title for n in all_notes}

    return templates.TemplateResponse(
        request,
        name="partials/task_row.html",
        context={"task": task, "notes_map": notes_map},
    )


@router.get("/tasks/hx/{task_id}/edit", response_class=HTMLResponse)
async def edit_task_form_hx(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
):
    """HTMX endpoint to return the inline edit form for a task."""
    task = db.get(Task, task_id)

    notes_stmt = select(Note).order_by(Note.title)
    all_notes = list(db.execute(notes_stmt).scalars().all())

    return templates.TemplateResponse(
        request,
        name="partials/task_edit_row.html",
        context={"task": task, "notes": all_notes},
    )


@router.post("/tasks/hx/{task_id}/edit", response_class=HTMLResponse)
async def update_task_hx(
    request: Request,
    task_id: int,
    title: str = Form(...),
    priority: str = Form("Medium"),
    due_date: str = Form(""),
    note_id: str = Form(""),
    db: Session = Depends(get_db),
):
    """HTMX endpoint to update a task inline and return the static row."""
    task = db.get(Task, task_id)
    if not task:
        return HTMLResponse("<tr><td colspan='6' class='text-rose-400'>Task not found</td></tr>", status_code=404)
    
    dt = None
    if due_date:
        dt = datetime.strptime(due_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    parsed_note_id = int(note_id) if note_id and note_id.strip() else None

    task.title = title
    task.priority = TaskPriority(priority)
    task.due_date = dt
    task.note_id = parsed_note_id

    db.commit()
    db.refresh(task)

    notes_stmt = select(Note)
    all_notes = list(db.execute(notes_stmt).scalars().all())
    notes_map = {n.id: n.title for n in all_notes}

    return templates.TemplateResponse(
        request,
        name="partials/task_row.html",
        context={"task": task, "notes_map": notes_map},
    )


@router.delete("/tasks/hx/{task_id}", response_class=HTMLResponse)
async def delete_task_hx(
    task_id: int,
    db: Session = Depends(get_db),
):
    """HTMX endpoint to delete a task."""
    task = db.get(Task, task_id)
    if task:
        db.delete(task)
        db.commit()
    return HTMLResponse("")


@router.delete("/tasks/hx/recurring/{rule_id}", response_class=HTMLResponse)
async def delete_rule_hx(
    rule_id: int,
    db: Session = Depends(get_db),
):
    """
    HTMX endpoint to delete a recurring rule.
    Cascading will handle linked tasks or they become orphaned depending on DB config.
    """
    rule = db.get(RecurringRule, rule_id)
    if rule:
        db.delete(rule)
        db.commit()
    return HTMLResponse("")


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


@router.get("/bookmarks/hx/{bookmark_id}", response_class=HTMLResponse)
async def get_bookmark_hx(
    request: Request,
    bookmark_id: int,
    db: Session = Depends(get_db),
):
    """HTMX endpoint to return the static bookmark card (used to cancel edit)."""
    bookmark = db.get(Bookmark, bookmark_id)
    if not bookmark:
        return HTMLResponse("<div class='text-rose-400'>Bookmark not found</div>", status_code=404)
    return templates.TemplateResponse(
        request,
        name="partials/bookmark_card.html",
        context={"bookmark": bookmark},
    )


@router.get("/bookmarks/hx/{bookmark_id}/edit", response_class=HTMLResponse)
async def edit_bookmark_form_hx(
    request: Request,
    bookmark_id: int,
    db: Session = Depends(get_db),
):
    """HTMX endpoint to return the inline edit form for a bookmark."""
    bookmark = db.get(Bookmark, bookmark_id)
    return templates.TemplateResponse(
        request,
        name="partials/bookmark_edit_card.html",
        context={"bookmark": bookmark},
    )


@router.post("/bookmarks/hx/{bookmark_id}/edit", response_class=HTMLResponse)
async def update_bookmark_hx(
    request: Request,
    bookmark_id: int,
    title: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    """HTMX endpoint to update a bookmark inline and return the static card."""
    bookmark = db.get(Bookmark, bookmark_id)
    if not bookmark:
        return HTMLResponse("<div class='text-rose-400'>Bookmark not found</div>", status_code=404)
    bookmark.title = title
    bookmark.description = description
    
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
    month: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Render the expenses dashboard page.

    Computes financial metrics, fetches accounts (for form dropdowns),
    and recent transactions within the bounded month.
    """
    now = datetime.now(timezone.utc)

    # ── Parse or default target month ────────────────────────────────
    if month:
        try:
            target_date = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
            current_month_start = target_date
        except ValueError:
            current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    selected_month = current_month_start.strftime("%Y-%m")

    # ── Compute metrics ──────────────────────────────────────────────
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

    # ── Fetch recent transactions strictly within target month ───────
    txn_stmt = select(Transaction).where(
        Transaction.date >= current_month_start,
        Transaction.date < next_month_start
    ).order_by(Transaction.id.desc()).limit(50)
    recent_txns = list(db.execute(txn_stmt).scalars().all())

    return templates.TemplateResponse(
        request,
        name="expenses.html",
        context={
            "metrics": metrics,
            "category_breakdown_json": breakdown_json,
            "accounts": all_accounts,
            "transactions": recent_txns,
            "selected_month": selected_month,
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

    # Generate the updated markdown preview
    rendered_html = _render_markdown(note.content) if note.content else ""
    preview_html = templates.get_template("partials/note_preview.html").render(
        {"rendered_html": rendered_html}
    )
    
    # Inject OOB attribute so HTMX hot-swaps the preview panel
    preview_html = preview_html.replace(
        'id="note-preview-content"', 
        'id="note-preview-content" hx-swap-oob="outerHTML"'
    )

    feedback_html = f'<span class="text-emerald-400">✓ Saved at {datetime.now().strftime("%H:%M:%S")}</span>'

    # Return both the feedback (normal swap) and the updated preview (OOB swap)
    return HTMLResponse(feedback_html + preview_html)


@router.post("/notes/hx/upload", response_class=HTMLResponse)
async def upload_asset_hx(
    file: UploadFile = File(...),
):
    """
    HTMX endpoint — process local file uploads for the PKB editor.
    Returns the markdown snippet for the image.
    """
    if not file.filename:
        return HTMLResponse('<span class="text-rose-400">No file provided</span>', status_code=400)
        
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg']:
        return HTMLResponse('<span class="text-rose-400">Invalid file type</span>', status_code=400)
        
    safe_filename = f"{uuid.uuid4().hex}{ext}"
    upload_dir = Path("src/static/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / safe_filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    markdown_snippet = f"![{file.filename}](/static/uploads/{safe_filename})"
    
    return HTMLResponse(
        f'<span class="text-emerald-400">Uploaded:</span> <code class="bg-surface-900 px-1 py-0.5 rounded ml-1 text-slate-300">{markdown_snippet}</code>'
    )
