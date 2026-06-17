"""Recurring task scheduler.

In Phase 6 we spawned the next occurrence inline when a task was
moved to "done".  This job handles the case where a recurring task
is past its deadline but never marked done (e.g. user went on
vacation) — we surface it in the assignee's inbox.

Run once an hour via Celery beat.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from app.database import SessionLocal
from app.models.notification import Notification
from app.models.task import Task


logger = logging.getLogger(__name__)


@dataclass
class SpawnResult:
    inspected: int
    reminders_sent: int


def spawn_due_recurring_tasks(now: datetime | None = None) -> SpawnResult:
    """Send a "recurring task is due" reminder for every recurring
    parent task whose latest occurrence is past deadline.

    We *don't* auto-spawn outside the "task done" flow because that
    would create ghost tasks nobody owns.  Instead we ping the
    assignee (or the project owner if unassigned) so they can decide.
    """
    now = now or datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        # Recurring parent tasks (no parent_task_id set) with a deadline
        parents: List[Task] = (
            db.query(Task)
            .filter(
                Task.recurrence.isnot(None),
                Task.recurrence != "none",
                Task.parent_task_id.is_(None),
            )
            .all()
        )
        reminders = 0
        inspected = 0
        for parent in parents:
            inspected += 1
            if not parent.deadline:
                continue
            deadline = parent.deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if deadline > now:
                continue
            # Find the latest occurrence (or fall back to the parent itself)
            latest = (
                db.query(Task)
                .filter(
                    (Task.id == parent.id) | (Task.parent_task_id == parent.id)
                )
                .order_by(Task.created_at.desc())
                .first()
            )
            if not latest or latest.status == "done":
                continue
            recipient = latest.assignee_id or parent.assignee_id
            if not recipient:
                continue
            # De-dupe: only send one reminder per (task, day)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            already = (
                db.query(Notification)
                .filter(
                    Notification.user_id == recipient,
                    Notification.type == "recurring.due",
                    Notification.link == f"/projects/{parent.project_id}/kanban",
                    Notification.created_at >= today_start,
                )
                .first()
            )
            if already:
                continue
            db.add(
                Notification(
                    user_id=recipient,
                    project_id=parent.project_id,
                    type="recurring.due",
                    title=f"🔁 Task định kỳ đến hạn: {parent.title}",
                    body=f"Deadline: {deadline.isoformat()}. Đánh dấu done để spawn occurrence tiếp theo.",
                    link=f"/projects/{parent.project_id}/kanban",
                )
            )
            reminders += 1
        db.commit()
        logger.info(
            "recurring_task_job: inspected=%d reminders_sent=%d",
            inspected,
            reminders,
        )
        return SpawnResult(inspected=inspected, reminders_sent=reminders)
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    print(spawn_due_recurring_tasks())
