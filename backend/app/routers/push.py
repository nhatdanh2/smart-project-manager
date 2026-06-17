"""Push device registration + admin broadcast endpoint."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.push import PushDevice, PushDeviceIn
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.push_service import send_to_user


logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"{settings.API_PREFIX}/push", tags=["push"])


@router.post("/tokens", status_code=201)
def register_token(
    payload: PushDeviceIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Register (or refresh) the current user's push token.

    Idempotent on token equality — we keep one row per token.
    """
    existing = db.query(PushDevice).filter(PushDevice.token == payload.token).first()
    if existing:
        existing.platform = payload.platform
        existing.device_name = payload.device_name
        existing.user_id = current.id
        db.add(existing)
    else:
        db.add(
            PushDevice(
                user_id=current.id,
                token=payload.token,
                platform=payload.platform,
                device_name=payload.device_name,
            )
        )
    db.commit()
    return {"status": "registered"}


@router.delete("/tokens/{token}")
def unregister_token(
    token: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    db.query(PushDevice).filter(
        PushDevice.user_id == current.id, PushDevice.token == token
    ).delete()
    db.commit()
    return {"status": "unregistered"}


class BroadcastIn(BaseModel):
    title: str
    body: str
    data: Optional[dict] = None


@router.post("/admin/broadcast")
def admin_broadcast(
    payload: BroadcastIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if current.role != "admin":
        raise HTTPException(403, detail="Admin only")
    from app.models.user import User as U

    users = db.query(U).filter(U.is_active == True).all()  # noqa: E712
    sent = 0
    for u in users:
        sent += send_to_user(db, u.id, title=payload.title, body=payload.body, data=payload.data)
    return {"users": len(users), "deliveries": sent}
