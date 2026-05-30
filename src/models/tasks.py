"""
Unified Tasks Engine — SQLAlchemy models.

Defines Task (with priority/status enums) and RecurringRule for
complex scheduling via iCalendar RRULE strings.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class TaskPriority(str, enum.Enum):
    """Priority levels for a task."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TaskStatus(str, enum.Enum):
    """Lifecycle states for a task."""

    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    MISSED = "Missed"


class Task(Base):
    """A single actionable item with priority, status, and optional scheduling."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority), nullable=False, default=TaskPriority.MEDIUM
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING
    )
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    project_tag: Mapped[str | None] = mapped_column(String, nullable=True)

    # Optional link to the RecurringRule that spawned this task
    rule_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("recurring_rules.id"), nullable=True
    )

    # Relationships
    rule: Mapped["RecurringRule | None"] = relationship(
        back_populates="tasks", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title='{self.title}', status={self.status.value})>"


class RecurringRule(Base):
    """
    An RRULE-based template that spawns Task instances on a schedule.

    * `is_strict=True`  → standard recurring task (must be completed each cycle).
    * `is_strict=False` → habit-style task (expires if not completed by next_due).
    """

    __tablename__ = "recurring_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_title: Mapped[str] = mapped_column(String, nullable=False)
    rrule_string: Mapped[str] = mapped_column(String, nullable=False)
    is_strict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    next_due: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="rule", lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<RecurringRule(id={self.id}, title='{self.task_title}', "
            f"strict={self.is_strict})>"
        )

