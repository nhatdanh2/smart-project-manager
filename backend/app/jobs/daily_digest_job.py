"""Daily digest job.

Sends one email per project member summarising:
* new tasks assigned in the last 24h
* tasks due in the next 48h
* overdue tasks

Run once a day at 08:00 local time via Celery beat.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.digest import DigestEmail
from app.models.project import ProjectMember
from app.models.task import Task


logger = logging.getLogger(__name__)


def _format_digest(user_name: str, project_title: str, lines: list[str]) -> tuple[str, str]:
    subject = f"[Smart PM] Daily digest · {project_title}"
    body = (
        f"Hi {user_name},\n\n"
        f"Here's your daily digest for project '{project_title}':\n\n"
        + "\n".join(f"  • {line}" for line in lines)
        + "\n\n— Smart PM"
    )
    return subject, body


def send_daily_digests() -> dict:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        sent = 0
        # Get every project that has at least one task in the window
        projects = (
            db.query(Task.project_id)
            .filter(Task.created_at >= now - timedelta(days=1))
            .distinct()
            .all()
        )
        for (project_id,) in projects:
            members = (
                db.query(ProjectMember)
                .filter(ProjectMember.project_id == project_id)
                .all()
            )
            for member in members:
                user_id = member.user_id
                # Need the user's email + name — query via join
                from app.models.user import User

                user = db.query(User).filter(User.id == user_id).first()
                if not user or not user.is_active:
                    continue

                new_tasks = (
                    db.query(Task)
                    .filter(
                        Task.assignee_id == user_id,
                        Task.project_id == project_id,
                        Task.created_at >= now - timedelta(days=1),
                    )
                    .all()
                )
                upcoming = (
                    db.query(Task)
                    .filter(
                        Task.assignee_id == user_id,
                        Task.project_id == project_id,
                        Task.status != "done",
                        Task.deadline != None,  # noqa: E711
                        Task.deadline <= now + timedelta(days=2),
                    )
                    .all()
                )
                overdue = [
                    t for t in upcoming
                    if t.deadline and t.deadline < now and t.status != "done"
                ]
                if not new_tasks and not upcoming and not overdue:
                    continue

                lines = []
                if new_tasks:
                    lines.append(f"{len(new_tasks)} new task(s): " + ", ".join(t.title for t in new_tasks[:5]))
                if upcoming:
                    lines.append(f"{len(upcoming)} due in 48h")
                if overdue:
                    lines.append(f"⚠ {len(overdue)} overdue")
                from app.models.project import Project

                project = db.query(Project).filter(Project.id == project_id).first()
                project_title = project.title if project else "(project)"
                subject, body = _format_digest(user.name, project_title, lines)
                db.add(
                    DigestEmail(
                        project_id=project_id,
                        recipient=user.email,
                        subject=subject,
                        body=body,
                        delivery="logged",
                    )
                )
                sent += 1
        db.commit()
        logger.info("daily_digest: sent %d email(s)", sent)
        return {"sent": sent}
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    print(send_daily_digests())
