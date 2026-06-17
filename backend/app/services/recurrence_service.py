"""Recurrence helpers for tasks.

We support four common cadences (none/daily/weekly/biweekly/monthly)
which is enough for the student-project domain.  When a task is
completed, the next occurrence is generated automatically (with the
same title, description, assignee, story_points, priority, and
recurrence).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.task import Task, TaskHistory


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compute_next_deadline(
    current: Optional[datetime], recurrence: str
) -> Optional[datetime]:
    if not current or not recurrence or recurrence == "none":
        return None
    cur = _to_utc(current)
    if recurrence == "daily":
        return cur + timedelta(days=1)
    if recurrence == "weekly":
        return cur + timedelta(weeks=1)
    if recurrence == "biweekly":
        return cur + timedelta(weeks=2)
    if recurrence == "monthly":
        return cur + timedelta(days=30)
    return None


def spawn_next_occurrence(db: Session, task: Task) -> Optional[Task]:
    """Create the next occurrence of a recurring task.

    Called when a task is moved to ``done``.  Returns the new task
    (or ``None`` if the source task isn't recurring).
    """
    if not task.recurrence or task.recurrence == "none":
        return None
    # Only spawn if the source itself isn't a generated occurrence
    # to avoid runaway chains (we always spawn from the *parent*).
    if task.parent_task_id:
        return None

    next_deadline = compute_next_deadline(task.deadline, task.recurrence)
    new_task = Task(
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status="todo",
        story_points=task.story_points,
        priority=task.priority,
        assignee_id=task.assignee_id,
        deadline=next_deadline,
        recurrence=task.recurrence,
        parent_task_id=task.id,
        depends_on_json=None,  # occurrences don't carry deps
    )
    db.add(new_task)
    db.flush()
    db.add(
        TaskHistory(
            task_id=new_task.id,
            user_id=None,
            action="auto_spawned",
            new_value=f"parent={task.id}",
        )
    )
    db.commit()
    db.refresh(new_task)
    return new_task
