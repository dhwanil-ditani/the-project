"""
Lazy Evaluation Engine for the Unified Tasks system.

Called on dashboard access to process overdue tasks:
  1. Non-strict (habit) tasks past due → marked ``Missed``.
  2. Strict tasks past due → left ``Pending`` (overdue).
  3. For any rule whose latest task is ``Completed`` or ``Missed``,
     spawn the next occurrence using ``dateutil.rrule``.
"""

from datetime import datetime, timezone

from dateutil.rrule import rrulestr
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.tasks import RecurringRule, Task, TaskPriority, TaskStatus


def _compute_next_due(rrule_string: str, after: datetime) -> datetime | None:
    """
    Parse an RRULE string and return the first occurrence strictly
    after ``after``.  Returns ``None`` if the rule has no future dates.
    """
    try:
        rule = rrulestr(rrule_string, dtstart=after)
        next_dt = rule.after(after, inc=False)
        return next_dt
    except Exception:
        return None


def _spawn_next_task(db: Session, rule: RecurringRule, next_due: datetime) -> Task:
    """Create a new pending Task from a RecurringRule for the given due date."""
    task = Task(
        title=rule.task_title,
        priority=TaskPriority.MEDIUM,
        status=TaskStatus.PENDING,
        due_date=next_due,
        rule_id=rule.id,
    )
    db.add(task)
    return task


def evaluate_pending_tasks(db: Session) -> None:
    """
    Process all overdue pending tasks:

    * **Habits** (``rule.is_strict == False``): mark as ``Missed``.
    * **Strict tasks**: leave as ``Pending`` (they remain overdue).
    * Spawn next occurrence for any rule whose task is ``Completed``
      or newly ``Missed``.
    """
    now = datetime.now(timezone.utc)

    # ── Step 1: find all overdue pending tasks ──────────────────────────
    stmt = select(Task).where(
        Task.status == TaskStatus.PENDING,
        Task.due_date.isnot(None),
        Task.due_date < now,
    )
    overdue_tasks: list[Task] = list(db.execute(stmt).scalars().all())

    for task in overdue_tasks:
        if task.rule_id is None:
            # Standalone task — no rule logic applies
            continue

        rule = task.rule
        if rule is None:
            continue

        # Non-strict (habit) → mark missed
        if not rule.is_strict:
            task.status = TaskStatus.MISSED

    # Flush step 1 changes so step 2 queries see updated statuses
    db.flush()

    # ── Step 2: spawn next tasks for rules with resolved tasks ──────────
    # Gather all rules that have at least one Completed or Missed task
    rules_stmt = select(RecurringRule)
    all_rules: list[RecurringRule] = list(db.execute(rules_stmt).scalars().all())

    for rule in all_rules:
        # Check if the most recent task for this rule is terminal
        latest_task_stmt = (
            select(Task)
            .where(Task.rule_id == rule.id)
            .order_by(Task.id.desc())
            .limit(1)
        )
        latest_task = db.execute(latest_task_stmt).scalar_one_or_none()

        if latest_task is None:
            continue

        if latest_task.status not in (TaskStatus.COMPLETED, TaskStatus.MISSED):
            continue

        # Already has a pending successor? Skip.
        pending_exists_stmt = select(Task).where(
            Task.rule_id == rule.id,
            Task.status == TaskStatus.PENDING,
        )
        if db.execute(pending_exists_stmt).scalar_one_or_none() is not None:
            continue

        # Compute and spawn the next task
        next_due = _compute_next_due(rule.rrule_string, now)
        if next_due is not None:
            rule.next_due = next_due
            _spawn_next_task(db, rule, next_due)

    db.flush()
