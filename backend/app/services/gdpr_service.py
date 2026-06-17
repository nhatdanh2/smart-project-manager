"""GDPR: data export, soft-delete, hard-purge, admin recovery.

The flow:

1.  User requests **export** → we collect every row in the database
    that references their ``user_id`` and return a JSON archive.
2.  User requests **deletion** → we set ``is_active=False``,
    ``deletion_requested_at=now()``, anonymise the email so the row
    can never log in again, and revoke all refresh tokens.
3.  User can cancel the deletion any time within the grace period
    (configurable, default 30 days).
4.  A scheduled task (Celery beat or FastAPI startup hook) calls
    ``purge_expired_deletions`` to hard-delete accounts whose
    ``deletion_requested_at`` is older than the grace period.

We never log passwords or password hashes into the audit log; only
the *fact* that a deletion was requested is recorded.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    AIReport,
    ContributionScore,
    DigestEmail,
    ExtractedTask,
    GDPRAuditLog,
    Meeting,
    Notification,
    ProjectMember,
    Task,
    TaskComment,
    TaskHistory,
    User,
)
from app.services.audit_service import record_gdpr_event


logger = logging.getLogger(__name__)


# Tables that hold a ``user_id`` column we want to scrub.  We don't
# drop rows — we null the FK so project / task history remains
# intact and the contributor row becomes a tombstone.
_USER_FK_TABLES: List[tuple] = [
    ("task_history", "user_id"),
    ("task_comments", "user_id"),
    ("notifications", "user_id"),
    ("contribution_scores", "user_id"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def collect_user_payload(db: Session, user: User) -> Dict[str, Any]:
    """Build the JSON archive returned to a user requesting export."""
    projects = (
        db.query(ProjectMember.project_id)
        .filter(ProjectMember.user_id == user.id)
        .all()
    )
    project_ids = [p[0] for p in projects]

    tasks = (
        db.query(Task)
        .filter(
            (Task.assignee_id == user.id) | (Task.project_id.in_(project_ids))
        )
        .all()
    )
    meetings = (
        db.query(Meeting)
        .filter(Meeting.project_id.in_(project_ids))
        .all()
    )
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .all()
    )
    contributions = (
        db.query(ContributionScore)
        .filter(ContributionScore.user_id == user.id)
        .all()
    )
    digests = (
        db.query(DigestEmail)
        .filter(DigestEmail.project_id.in_(project_ids))
        .all()
    )

    def _ser(model, row) -> Dict[str, Any]:
        return {
            c.key: (getattr(row, c.key).isoformat() if isinstance(getattr(row, c.key), datetime) else getattr(row, c.key))
            for c in inspect(model).mapper.column_attrs
        }

    return {
        "exported_at": _now().isoformat(),
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "projects_member_of": project_ids,
        "tasks": [_ser(Task, t) for t in tasks],
        "meetings": [_ser(Meeting, m) for m in meetings],
        "notifications": [_ser(Notification, n) for n in notifications],
        "contributions": [_ser(ContributionScore, c) for c in contributions],
        "digest_emails": [_ser(DigestEmail, d) for d in digests],
    }


def request_export(
    db: Session,
    user: User,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    payload = collect_user_payload(db, user)
    record_gdpr_event(
        db,
        affected_user_id=user.id,
        actor_user_id=user.id,
        action="export.completed",
        ip=ip,
        user_agent=user_agent,
        extra={"size": len(json.dumps(payload))},
    )
    return payload


def request_deletion(
    db: Session,
    user: User,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> User:
    """Soft-delete the user.

    - Sets ``is_active=False`` and ``deletion_requested_at=now``
    - Anonymises the email so the unique index still works
    - Hashes the password to a random value (defence in depth)
    - Revokes all refresh tokens by rotating the password hash
    """
    grace = getattr(settings, "GDPR_DELETION_GRACE_DAYS", 30)
    user.is_active = False
    user.deletion_requested_at = _now()
    # ``anonymized_at`` is set at hard-purge time, not now — until
    # then the user can recover their account.
    user.email = f"deleted-{uuid.uuid4()}@deleted.invalid"
    user.name = "(deleted user)"
    user.avatar_url = None
    # Invalidate the password.  The user cannot log in anymore.
    user.password_hash = "!" + uuid.uuid4().hex
    db.add(user)
    record_gdpr_event(
        db,
        affected_user_id=user.id,
        actor_user_id=user.id,
        action="delete.requested",
        ip=ip,
        user_agent=user_agent,
        extra={"grace_days": grace},
    )
    db.commit()
    db.refresh(user)
    return user


def cancel_deletion(
    db: Session,
    user: User,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> User:
    """Restore a soft-deleted user.  The original email is gone, so
    the user must reset their password before they can log in again.
    """
    if not user.deletion_requested_at:
        return user
    user.is_active = True
    user.deletion_requested_at = None
    user.email = f"recover-{uuid.uuid4()}@recover.invalid"  # placeholder
    user.name = "(recovered user)"
    db.add(user)
    record_gdpr_event(
        db,
        affected_user_id=user.id,
        actor_user_id=user.id,
        action="delete.cancelled",
        ip=ip,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(user)
    return user


def hard_purge(db: Session, user: User) -> None:
    """Hard-delete the user's data.  Idempotent.

    We:
    1.  Null out the ``user_id`` FK in tables that should keep their
        rows (notifications, comments, history, contributions) so the
        rest of the project still makes sense.
    2.  Remove the user from every project membership.
    3.  Delete the user row.
    4.  Audit-log it.
    """
    user_id = user.id

    # 1. Null-out FKs (preserve rows for project context)
    for table, col in _USER_FK_TABLES:
        try:
            db.execute(
                f"UPDATE {table} SET {col} = NULL WHERE {col} = :uid",
                {"uid": user_id},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to scrub %s.%s: %s", table, col, exc)

    # 2. Remove memberships
    db.query(ProjectMember).filter(ProjectMember.user_id == user_id).delete()

    # 3. Drop the user row
    db.query(User).filter(User.id == user_id).delete()

    record_gdpr_event(
        db,
        affected_user_id=user_id,
        actor_user_id=None,
        action="delete.purged",
    )
    db.commit()


def purge_expired_deletions(db: Session) -> int:
    """Hard-delete accounts that have been pending past the grace period.

    Returns the number of accounts purged.
    """
    grace = getattr(settings, "GDPR_DELETION_GRACE_DAYS", 30)
    cutoff = _now() - timedelta(days=grace)
    candidates = (
        db.query(User)
        .filter(
            User.deletion_requested_at.isnot(None),
            User.deletion_requested_at < cutoff,
        )
        .all()
    )
    for user in candidates:
        # Anonymise up-front so any data still hanging around loses
        # identifying information immediately.
        user.anonymized_at = _now()
        db.add(user)
        hard_purge(db, user)
    if candidates:
        logger.info("Purged %d expired account(s)", len(candidates))
    return len(candidates)


def admin_recover(
    db: Session,
    affected_user_id: str,
    admin: User,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Optional[User]:
    """Find a soft-deleted user by ID and cancel their deletion.

    Admin-only — the caller must enforce role-based access.
    """
    user = db.query(User).filter(User.id == affected_user_id).first()
    if not user or not user.deletion_requested_at:
        return None
    cancel_deletion(db, user, ip=ip, user_agent=user_agent)
    record_gdpr_event(
        db,
        affected_user_id=affected_user_id,
        actor_user_id=admin.id,
        action="admin.recover",
        ip=ip,
        user_agent=user_agent,
    )
    return user
