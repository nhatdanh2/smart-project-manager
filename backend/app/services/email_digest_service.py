"""Email digest service.

Renders a weekly summary of project activity and "sends" it to the
project members.  In Phase 3 we don't have a real SMTP transport - the
service writes a structured log line and persists a record to the
``digest_emails`` table so the frontend can preview what was sent.

To wire up real SMTP, set the following env vars and extend
``_send_email`` to call aiosmtplib or similar:

- ``SMTP_HOST``
- ``SMTP_PORT``
- ``SMTP_USER``
- ``SMTP_PASSWORD``
- ``SMTP_FROM`` (default = SMTP_USER)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.models.digest import DigestEmail
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskHistory
from app.models.user import User
from app.services.cpm_service import CPMTaskInput, calculate_cpm
from app.services.contribution_service import (
    MemberTaskStats,
    calculate_contribution,
)


logger = logging.getLogger(__name__)


SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))


def _send_email(recipient: str, subject: str, body: str) -> str:
    """Send the email.  In Phase 3 we just log it and return ``"logged"``.

    Replace this with real SMTP integration in production.  The function
    is intentionally simple so unit tests can monkey-patch it.
    """
    if SMTP_HOST:
        # Place real SMTP send here.
        # E.g. aiosmtplib.send(...)
        logger.info(
            "SMTP would send to %s | subject=%s | body_len=%d",
            recipient,
            subject,
            len(body),
        )
        return "sent"
    logger.info("[DIGEST] to=%s subject=%s body_len=%d", recipient, subject, len(body))
    return "logged"


def _build_digest_body(project: Project, data: Dict) -> Tuple[str, str]:
    """Return (subject, body) for a digest email."""
    days = data["days"]
    completed = data["completed_this_week"]
    created = data["created_this_week"]
    overdue = data["overdue_count"]
    members = data["member_summaries"]

    subject = f"[SPM] Tuần {days[0].strftime('%d/%m')} - {days[-1].strftime('%d/%m')}: {project.title}"

    lines: List[str] = []
    lines.append(f"Đồ án: {project.title}")
    lines.append(f"Deadline: {project.deadline.strftime('%d/%m/%Y')}")
    lines.append("")
    lines.append(f"Trong {len(days)} ngày qua:")
    lines.append(f"  - Task hoàn thành: {completed}")
    lines.append(f"  - Task mới tạo:    {created}")
    lines.append(f"  - Task quá hạn:    {overdue}")
    lines.append("")
    lines.append("Đóng góp từng thành viên (toàn dự án):")
    for m in members:
        bar = "█" * int(m["contribution_percent"] / 5) + "░" * (20 - int(m["contribution_percent"] / 5))
        lines.append(f"  {m['name']:<24} {bar} {m['contribution_percent']:5.1f}%")
    if data.get("cpm_delay_risk") is not None:
        risk = data["cpm_delay_risk"]
        if risk >= 0.7:
            verdict = "⚠ Nguy cơ trễ cao"
        elif risk >= 0.3:
            verdict = "Cần chú ý"
        else:
            verdict = "Đúng tiến độ"
        lines.append("")
        lines.append(f"CPM: dự kiến hoàn thành trong {data['cpm_duration']} ngày · {verdict}")
    lines.append("")
    lines.append("-- Smart Student Project Manager")
    return subject, "\n".join(lines)


def _collect_week_data(
    db: Session, project: Project, week_start: datetime
) -> Dict:
    # Normalise both ends to UTC-aware datetimes so we can compare
    # safely with columns that may be either naive (SQLite) or aware
    # (Postgres).
    if week_start.tzinfo is None:
        week_start = week_start.replace(tzinfo=timezone.utc)
    week_end = week_start + timedelta(days=7)
    tasks = db.query(Task).filter(Task.project_id == project.id).all()

    def _aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    ws = _aware(week_start)
    we = _aware(week_end)
    completed = sum(
        1
        for t in tasks
        if t.completed_at
        and ws <= _aware(t.completed_at) < we
    )
    created = sum(
        1
        for t in tasks
        if ws <= _aware(t.created_at) < we
    )
    now = datetime.now(tz=timezone.utc)
    overdue = sum(
        1
        for t in tasks
        if t.deadline
        and t.status != "done"
        and (t.deadline if t.deadline.tzinfo else t.deadline.replace(tzinfo=timezone.utc)) < now
    )

    members = (
        db.query(User)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .filter(ProjectMember.project_id == project.id)
        .all()
    )
    histories = (
        db.query(TaskHistory)
        .join(Task, Task.id == TaskHistory.task_id)
        .filter(Task.project_id == project.id)
        .all()
    )
    stats: List[MemberTaskStats] = []
    for u in members:
        ut = [t for t in tasks if t.assignee_id == u.id]
        uc = [t for t in ut if t.status == "done"]
        on_time = 0
        for t in uc:
            if t.deadline and t.completed_at:
                dl = t.deadline if t.deadline.tzinfo else t.deadline.replace(tzinfo=timezone.utc)
                ca = t.completed_at if t.completed_at.tzinfo else t.completed_at.replace(tzinfo=timezone.utc)
                if ca <= dl:
                    on_time += 1
        uh = [h for h in histories if h.user_id == u.id]
        last = max(
            ([h.created_at for h in uh] + [t.created_at for t in ut]),
            default=None,
        )
        stats.append(
            MemberTaskStats(
                user_id=u.id,
                tasks_completed=len(uc),
                tasks_assigned=len(ut),
                story_points_completed=sum(t.story_points for t in uc),
                story_points_assigned=sum(t.story_points for t in ut),
                on_time_completed=on_time,
                activity_count=len(uh),
                last_activity=last,
            )
        )
    results = calculate_contribution(stats)

    cpm = calculate_cpm(
        tasks=[
            CPMTaskInput(
                id=t.id,
                title=t.title,
                story_points=t.story_points,
                depends_on=t.depends_on,
            )
            for t in tasks
        ],
        deadline=project.deadline,
    )

    return {
        "days": [week_start + timedelta(days=i) for i in range(7)],
        "completed_this_week": completed,
        "created_this_week": created,
        "overdue_count": overdue,
        "member_summaries": [
            {
                "user_id": r.user_id,
                "name": next((u.name for u in members if u.id == r.user_id), "?"),
                "contribution_percent": r.percent,
            }
            for r in results
        ],
        "cpm_duration": cpm.project_duration,
        "cpm_delay_risk": cpm.delay_risk,
    }


def send_digest(
    db: Session, project: Project, week_start: datetime
) -> List[DigestEmail]:
    """Compose and "send" the digest to every project member.

    Persists one ``DigestEmail`` row per recipient so the frontend can
    show a preview of what was delivered.
    """
    data = _collect_week_data(db, project, week_start)
    subject, body = _build_digest_body(project, data)
    members = (
        db.query(User)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .filter(ProjectMember.project_id == project.id)
        .all()
    )
    sent: List[DigestEmail] = []
    for m in members:
        delivery = _send_email(m.email, subject, body)
        row = DigestEmail(
            project_id=project.id,
            recipient=m.email,
            subject=subject,
            body=body,
            delivery=delivery,
        )
        db.add(row)
        db.flush()
        sent.append(row)
    db.commit()
    for row in sent:
        db.refresh(row)

    # Webhook broadcast (Slack/Discord/Teams).  Fire-and-forget; we just
    # log results and don't fail the digest send if webhooks are down.
    if sent:
        try:
            import asyncio
            from app.services.webhook_service import broadcast_digest

            first = sent[0]
            results = asyncio.run(broadcast_digest(db, first))
            for r in results:
                logger.info("Webhook delivery: %s -> %s", r["url"], r["ok"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Webhook broadcast failed: %s", exc)
    return sent
