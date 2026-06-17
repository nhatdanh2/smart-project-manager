"""Notification helpers.

Create notifications and (when possible) push them to the user via the
WebSocket hub so the bell UI can update in real time.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.services.realtime import get_hub


logger = logging.getLogger(__name__)


def notify(
    db: Session,
    *,
    user_id: str,
    type: str,
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Notification:
    """Create a notification and try to push it over WebSocket."""
    notif = Notification(
        user_id=user_id,
        project_id=project_id,
        type=type,
        title=title,
        body=body,
        link=link,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    try:
        hub = get_hub()
        hub.push_to_user(
            user_id,
            {
                "type": "notification",
                "id": notif.id,
                "title": notif.title,
                "body": notif.body,
                "link": notif.link,
                "projectId": notif.project_id,
                "notifType": notif.type,
                "createdAt": notif.created_at.isoformat()
                if notif.created_at
                else None,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Notification push failed: %s", exc)
    # Mobile push (best effort)
    try:
        from app.services.push_service import send_to_user

        send_to_user(
            db,
            user_id,
            title=notif.title,
            body=notif.body or "",
            data={"link": notif.link, "type": notif.type},
        )
    except Exception:
        pass
    return notif


def notify_project_members(
    db: Session,
    *,
    project_id: str,
    type: str,
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
    exclude_user_id: Optional[str] = None,
) -> List[Notification]:
    """Send the same notification to every member of a project."""
    from app.models.project import ProjectMember

    pm_rows = (
        db.query(ProjectMember).filter(ProjectMember.project_id == project_id).all()
    )
    out: List[Notification] = []
    for pm in pm_rows:
        if exclude_user_id and pm.user_id == exclude_user_id:
            continue
        out.append(
            notify(
                db,
                user_id=pm.user_id,
                type=type,
                title=title,
                body=body,
                link=link,
                project_id=project_id,
            )
        )
    return out
