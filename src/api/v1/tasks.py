"""
Tasks API — CRUD endpoints for Tasks, RecurringRules, and the Dashboard.

Mounted at ``/api/v1/tasks`` via the v1 router.
The ``/dashboard/today`` endpoint triggers the lazy evaluation engine
before returning today's action items.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.tasks import RecurringRule, Task, TaskPriority, TaskStatus
from src.schemas.tasks import (
    ActionItem,
    RecurringRuleCreate,
    RecurringRuleResponse,
    RecurringRuleUpdate,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from src.services.task_engine import evaluate_pending_tasks

router = APIRouter(tags=["tasks"])

# ── Priority sort order (High → Low) ───────────────────────────────────────
_PRIORITY_ORDER = {
    TaskPriority.HIGH: 0,
    TaskPriority.MEDIUM: 1,
    TaskPriority.LOW: 2,
}


# ═══════════════════════════════════════════════════════════════════════════
#  Task CRUD
# ═══════════════════════════════════════════════════════════════════════════

def _get_task_or_404(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found",
        )
    return task


@router.post("/tasks/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
) -> Task:
    """Create a new task."""
    task = Task(
        title=payload.title,
        description=payload.description,
        priority=TaskPriority(payload.priority),
        status=TaskStatus(payload.status),
        due_date=payload.due_date,
        project_tag=payload.project_tag,
        rule_id=payload.rule_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/tasks/", response_model=list[TaskResponse])
async def list_tasks(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[Task]:
    """Return a paginated list of all tasks."""
    stmt = select(Task).offset(skip).limit(limit).order_by(Task.id.desc())
    return list(db.execute(stmt).scalars().all())


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> Task:
    """Retrieve a single task by ID."""
    return _get_task_or_404(db, task_id)


@router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
) -> Task:
    """Update an existing task. Only provided fields are changed."""
    task = _get_task_or_404(db, task_id)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field == "priority" and value is not None:
            value = TaskPriority(value)
        elif field == "status" and value is not None:
            value = TaskStatus(value)
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a task by ID."""
    task = _get_task_or_404(db, task_id)
    db.delete(task)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  RecurringRule CRUD
# ═══════════════════════════════════════════════════════════════════════════

def _get_rule_or_404(db: Session, rule_id: int) -> RecurringRule:
    rule = db.get(RecurringRule, rule_id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RecurringRule with id {rule_id} not found",
        )
    return rule


@router.post(
    "/recurring/", response_model=RecurringRuleResponse, status_code=status.HTTP_201_CREATED
)
async def create_recurring_rule(
    payload: RecurringRuleCreate,
    db: Session = Depends(get_db),
) -> RecurringRule:
    """Create a new recurring rule."""
    rule = RecurringRule(
        task_title=payload.task_title,
        rrule_string=payload.rrule_string,
        is_strict=payload.is_strict,
    )
    if payload.next_due is not None:
        rule.next_due = payload.next_due

    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/recurring/", response_model=list[RecurringRuleResponse])
async def list_recurring_rules(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[RecurringRule]:
    """Return a paginated list of all recurring rules."""
    stmt = select(RecurringRule).offset(skip).limit(limit).order_by(RecurringRule.id.desc())
    return list(db.execute(stmt).scalars().all())


@router.get("/recurring/{rule_id}", response_model=RecurringRuleResponse)
async def get_recurring_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> RecurringRule:
    """Retrieve a single recurring rule by ID."""
    return _get_rule_or_404(db, rule_id)


@router.put("/recurring/{rule_id}", response_model=RecurringRuleResponse)
async def update_recurring_rule(
    rule_id: int,
    payload: RecurringRuleUpdate,
    db: Session = Depends(get_db),
) -> RecurringRule:
    """Update an existing recurring rule."""
    rule = _get_rule_or_404(db, rule_id)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/recurring/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recurring_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a recurring rule by ID."""
    rule = _get_rule_or_404(db, rule_id)
    db.delete(rule)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  Dashboard
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/dashboard/today", response_model=list[ActionItem])
async def dashboard_today(
    db: Session = Depends(get_db),
) -> list[ActionItem]:
    """
    Return today's action items.

    First triggers the lazy evaluation engine to process overdue tasks,
    then queries all pending tasks due today or earlier, sorted by
    priority (High → Low) then by due date (earliest first).
    """
    # Run the lazy evaluation engine
    evaluate_pending_tasks(db)
    db.commit()

    now = datetime.now(timezone.utc)

    # Pending tasks due today or earlier (including overdue)
    stmt = select(Task).where(
        Task.status == TaskStatus.PENDING,
        Task.due_date.isnot(None),
        Task.due_date <= now,
    )
    tasks: list[Task] = list(db.execute(stmt).scalars().all())

    # Also include pending tasks with no due_date (undated tasks)
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

    # Map to ActionItem, determining is_habit from the linked rule
    items: list[ActionItem] = []
    for task in tasks:
        is_habit = False
        if task.rule is not None:
            is_habit = not task.rule.is_strict

        items.append(
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

    return items
