"""
Pydantic schemas for the Unified Tasks Engine.

Covers Task CRUD, RecurringRule CRUD, and the unified ActionItem
schema used by the dashboard endpoint.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ── Task schemas ────────────────────────────────────────────────────────────
class TaskCreate(BaseModel):
    """Payload for creating a new task."""

    title: str
    description: str | None = None
    priority: str = "Medium"
    status: str = "Pending"
    due_date: datetime | None = None
    project_tag: str | None = None
    rule_id: int | None = None


class TaskUpdate(BaseModel):
    """Payload for updating an existing task. All fields optional."""

    title: str | None = None
    description: str | None = None
    priority: str | None = None
    status: str | None = None
    due_date: datetime | None = None
    project_tag: str | None = None


class TaskResponse(BaseModel):
    """Full task representation returned by the API."""

    id: int
    title: str
    description: str | None
    priority: str
    status: str
    due_date: datetime | None
    project_tag: str | None
    rule_id: int | None

    model_config = ConfigDict(from_attributes=True)


# ── RecurringRule schemas ───────────────────────────────────────────────────
class RecurringRuleCreate(BaseModel):
    """Payload for creating a new recurring rule."""

    task_title: str
    rrule_string: str
    is_strict: bool = True
    next_due: datetime | None = None


class RecurringRuleUpdate(BaseModel):
    """Payload for updating an existing recurring rule."""

    task_title: str | None = None
    rrule_string: str | None = None
    is_strict: bool | None = None
    next_due: datetime | None = None


class RecurringRuleResponse(BaseModel):
    """Full recurring rule representation returned by the API."""

    id: int
    task_title: str
    rrule_string: str
    is_strict: bool
    next_due: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Dashboard ActionItem schema ────────────────────────────────────────────
class ActionItem(BaseModel):
    """
    Unified dashboard item combining task data with habit metadata.

    ``is_habit`` is True when the task originates from a non-strict
    recurring rule (i.e. a habit that expires if not completed).
    """

    id: int
    title: str
    description: str | None
    priority: str
    status: str
    due_date: datetime | None
    project_tag: str | None
    rule_id: int | None
    is_habit: bool = False

    model_config = ConfigDict(from_attributes=True)
