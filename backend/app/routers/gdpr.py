"""User-facing GDPR endpoints (data export + account deletion) plus
admin recovery.

All routes require authentication; admin-only routes additionally
require ``role == "admin"`` on the JWT subject.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.gdpr_service import (
    admin_recover,
    cancel_deletion,
    hard_purge,
    purge_expired_deletions,
    request_deletion,
    request_export,
)


router = APIRouter(prefix=f"{settings.API_PREFIX}/gdpr", tags=["gdpr"])


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


@router.get("/export")
def export_my_data(
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Response:
    """Return a JSON archive of everything we have about the caller.

    The body is small enough to inline; for very large accounts a
    future iteration can write the file to S3 and return a signed URL.
    """
    payload = request_export(db, current, request=request)
    body = json.dumps(payload, indent=2, default=str)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="smart-pm-data-export.json"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/delete", status_code=status.HTTP_202_ACCEPTED)
def request_account_deletion(
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    """Soft-delete the caller's account.

    Sets ``is_active=False`` and ``deletion_requested_at=now``.  The
    account is hard-purged by the scheduled job after the grace
    period (default 30 days, configurable via
    ``GDPR_DELETION_GRACE_DAYS``).
    """
    if current.deletion_requested_at:
        raise HTTPException(status_code=409, detail="Deletion already requested")
    grace = getattr(settings, "GDPR_DELETION_GRACE_DAYS", 30)
    user = request_deletion(db, current, request=request)
    return {
        "status": "scheduled",
        "deletion_requested_at": user.deletion_requested_at.isoformat(),
        "purge_after_days": grace,
        "message": (
            f"Account will be permanently deleted in {grace} days. "
            "POST to /gdpr/cancel to abort."
        ),
    }


@router.post("/cancel", status_code=status.HTTP_200_OK)
def cancel_account_deletion(
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    if not current.deletion_requested_at:
        raise HTTPException(status_code=400, detail="No pending deletion to cancel")
    cancel_deletion(db, current, request=request)
    return {"status": "recovered"}


@router.post("/admin/recover/{user_id}")
def admin_recover_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    _require_admin(current)
    user = admin_recover(db, user_id, current, request=request)
    if not user:
        raise HTTPException(status_code=404, detail="No pending deletion for that user")
    return {"status": "recovered", "user_id": user.id}


@router.post("/admin/purge-expired")
def admin_purge_expired(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    """Manually trigger the scheduled purge (useful for cron-jobs in dev)."""
    _require_admin(current)
    n = purge_expired_deletions(db)
    return {"purged": n}
