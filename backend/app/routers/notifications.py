"""Notifications router."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.user import NotificationOut
from app.services.auth_service import get_current_user


router = APIRouter(prefix=f"{settings.API_PREFIX}/notifications", tags=["notifications"])


@router.get("", response_model=List[NotificationOut])
def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    only_unread: bool = False,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[NotificationOut]:
    q = db.query(Notification).filter(Notification.user_id == current.id)
    if only_unread:
        q = q.filter(Notification.is_read == False)  # noqa: E712
    rows = q.order_by(Notification.created_at.desc()).limit(limit).all()
    return [NotificationOut.model_validate(r) for r in rows]


@router.get("/unread-count", response_model=dict)
def unread_count(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    count = (
        db.query(Notification)
        .filter(Notification.user_id == current.id, Notification.is_read == False)  # noqa: E712
        .count()
    )
    return {"count": count}


@router.post("/{notif_id}/read", response_model=NotificationOut)
def mark_read(
    notif_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationOut:
    row = (
        db.query(Notification)
        .filter(Notification.id == notif_id, Notification.user_id == current.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    row.is_read = True
    db.commit()
    db.refresh(row)
    return NotificationOut.model_validate(row)


@router.post("/read-all", response_model=dict)
def mark_all_read(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    n = (
        db.query(Notification)
        .filter(Notification.user_id == current.id, Notification.is_read == False)  # noqa: E712
        .update({"is_read": True})
    )
    db.commit()
    return {"updated": n}
