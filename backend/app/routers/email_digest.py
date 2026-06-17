"""Email digest router.

Allows project members to trigger (and preview) a weekly digest email.
In dev the email is logged to stdout; production should plug a real
SMTP transport in ``services/email_digest_service._send_email``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.digest import DigestEmail
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.user import DigestEmailOut
from app.services.auth_service import get_current_user
from app.services.email_digest_service import (
    _build_digest_body,
    _collect_week_data,
    send_digest,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix=f"{settings.API_PREFIX}", tags=["email"])


def _ensure_member(db: Session, project_id: str, user_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pm = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        .first()
    )
    if not pm:
        raise HTTPException(status_code=403, detail="Not a project member")
    return project


@router.post(
    "/projects/{project_id}/digest/send",
    response_model=List[DigestEmailOut],
    status_code=201,
)
def send_digest_endpoint(
    project_id: str,
    days_ago: int = Query(7, ge=0, le=60),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[DigestEmailOut]:
    """Compose and "send" the weekly digest.  In dev the body is logged."""
    project = _ensure_member(db, project_id, current.id)
    week_start = datetime.now(tz=timezone.utc) - timedelta(days=days_ago)
    rows = send_digest(db, project, week_start)
    return [DigestEmailOut.model_validate(r) for r in rows]


@router.get(
    "/projects/{project_id}/digest/preview",
    response_model=DigestEmailOut,
)
def preview_digest(
    project_id: str,
    days_ago: int = Query(7, ge=0, le=60),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DigestEmailOut:
    """Render the digest body without sending it."""
    project = _ensure_member(db, project_id, current.id)
    week_start = datetime.now(tz=timezone.utc) - timedelta(days=days_ago)
    data = _collect_week_data(db, project, week_start)
    subject, body = _build_digest_body(project, data)
    return DigestEmailOut(
        id="preview",
        project_id=project.id,
        subject=subject,
        body=body,
        recipient=current.email,
        sent_at=datetime.now(tz=timezone.utc),
        delivery="preview",
    )


@router.get(
    "/projects/{project_id}/digest/history",
    response_model=List[DigestEmailOut],
)
def digest_history(
    project_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[DigestEmailOut]:
    _ensure_member(db, project_id, current.id)
    rows = (
        db.query(DigestEmail)
        .filter(DigestEmail.project_id == project_id)
        .order_by(DigestEmail.sent_at.desc())
        .limit(50)
        .all()
    )
    return [DigestEmailOut.model_validate(r) for r in rows]


class WebhookListUpdate(BaseModel):
    webhooks: list  # List[str]


class WebhookListOut(BaseModel):
    webhooks: list


@router.get(
    "/projects/{project_id}/webhooks",
    response_model=WebhookListOut,
)
def list_webhooks(
    project_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WebhookListOut:
    import json

    project = _ensure_member(db, project_id, current.id)
    raw = project.settings_json or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {}
    return WebhookListOut(webhooks=parsed.get("webhooks", []) or [])


@router.put(
    "/projects/{project_id}/webhooks",
    response_model=WebhookListOut,
)
def set_webhooks(
    project_id: str,
    payload: WebhookListUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WebhookListOut:
    """Replace the list of webhook URLs for a project (leader only)."""
    import json

    project = _ensure_member(db, project_id, current.id)
    pm = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current.id,
        )
        .first()
    )
    if not pm or pm.role != "leader":
        raise HTTPException(status_code=403, detail="Only the leader can manage webhooks")
    # Sanitise: only accept http(s) URLs
    cleaned = []
    for url in payload.webhooks:
        url = str(url).strip()
        if url and (url.startswith("http://") or url.startswith("https://")):
            cleaned.append(url)
    project.settings_json = json.dumps({"webhooks": cleaned})
    db.commit()
    return WebhookListOut(webhooks=cleaned)
