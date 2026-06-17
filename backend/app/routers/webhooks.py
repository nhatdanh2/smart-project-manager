"""Per-project webhook subscriptions + delivery log endpoints."""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.project import ProjectMember
from app.models.user import User
from app.models.webhook import WebhookDelivery, WebhookSubscription
from app.services.auth_service import get_current_user
from app.services.webhook_service import ALL_EVENTS, generate_secret


# NOTE: We deliberately avoid the bare ``/webhooks`` suffix because the
# older ``email_digest.router`` already exposes ``GET/PUT /projects/{id}/webhooks``
# for the legacy "list of URLs stored in project.settings_json" feature.
# Using a more specific path here keeps the two APIs from colliding and
# lets the dedicated subscriptions API (with HMAC signing, retry, deliveries)
# evolve independently.
router = APIRouter(prefix=f"{settings.API_PREFIX}/projects/{{project_id}}/webhook-subscriptions", tags=["webhooks"])


# -------- schemas --------
class WebhookCreate(BaseModel):
    target: str = Field("generic", pattern="^(generic|slack|discord)$")
    url: HttpUrl
    events: Optional[List[str]] = None
    is_active: bool = True


class WebhookOut(BaseModel):
    id: str
    target: str
    url: str
    events: Optional[List[str]]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookSecretOut(BaseModel):
    id: str
    target: str
    url: str
    events: Optional[List[str]]
    is_active: bool
    created_at: datetime
    secret: str  # ONLY returned at create / rotate time


class DeliveryOut(BaseModel):
    id: str
    event: str
    status: str
    attempts: int
    last_status_code: Optional[int]
    last_response: Optional[str]
    next_retry_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# -------- helpers --------
def _ensure_member(db: Session, project_id: str, user_id: str) -> None:
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


# -------- routes --------
@router.get("", response_model=List[WebhookOut])
def list_webhooks(
    project_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_member(db, project_id, current.id)
    return (
        db.query(WebhookSubscription)
        .filter(WebhookSubscription.project_id == project_id)
        .order_by(WebhookSubscription.created_at.desc())
        .all()
    )


@router.post("", response_model=WebhookSecretOut, status_code=201)
def create_webhook(
    project_id: str,
    payload: WebhookCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_member(db, project_id, current.id)
    if payload.events:
        bad = [e for e in payload.events if e not in ALL_EVENTS]
        if bad:
            raise HTTPException(400, detail=f"Unknown event(s): {bad}. Valid: {ALL_EVENTS}")
    sub = WebhookSubscription(
        project_id=project_id,
        target=payload.target,
        url=str(payload.url),
        secret=generate_secret(),
        events=payload.events,
        is_active=payload.is_active,
        created_by=current.id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/{webhook_id}/rotate", response_model=WebhookSecretOut)
def rotate_webhook_secret(
    project_id: str,
    webhook_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_member(db, project_id, current.id)
    sub = (
        db.query(WebhookSubscription)
        .filter(
            WebhookSubscription.id == webhook_id,
            WebhookSubscription.project_id == project_id,
        )
        .first()
    )
    if not sub:
        raise HTTPException(404, detail="Webhook not found")
    sub.secret = generate_secret()
    db.commit()
    db.refresh(sub)
    return sub


@router.delete("/{webhook_id}", status_code=204)
def delete_webhook(
    project_id: str,
    webhook_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_member(db, project_id, current.id)
    sub = (
        db.query(WebhookSubscription)
        .filter(
            WebhookSubscription.id == webhook_id,
            WebhookSubscription.project_id == project_id,
        )
        .first()
    )
    if not sub:
        raise HTTPException(404, detail="Webhook not found")
    db.delete(sub)
    db.commit()


@router.get("/{webhook_id}/deliveries", response_model=List[DeliveryOut])
def list_deliveries(
    project_id: str,
    webhook_id: str,
    limit: int = Query(50, ge=1, le=200),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_member(db, project_id, current.id)
    return (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.subscription_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/events")
def list_events():
    return {"events": ALL_EVENTS}


# ----- global router for non-project-scoped lookups (e.g. event names) -----
global_router = APIRouter(prefix=f"{settings.API_PREFIX}/webhooks", tags=["webhooks"])


@global_router.get("/events")
def list_all_events():
    """Public list of valid webhook event names (no auth required)."""
    return {"events": ALL_EVENTS}
