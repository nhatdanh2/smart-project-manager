"""Helpers to write GDPR-relevant events into the audit log."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.gdpr_audit import GDPRAuditLog


logger = logging.getLogger(__name__)


def _client_meta(request: Optional[Request]) -> Dict[str, str]:
    if request is None or not request.client:
        return {"ip": "", "user_agent": ""}
    return {
        "ip": request.client.host or "",
        "user_agent": (request.headers.get("user-agent") or "")[:500],
    }


def record_gdpr_event(
    db: Session,
    *,
    affected_user_id: str,
    action: str,
    actor_user_id: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> GDPRAuditLog:
    """Write a row to ``gdpr_audit_logs`` and flush.

    Pulls IP/UA from the request if not explicitly given.
    """
    meta = _client_meta(request)
    row = GDPRAuditLog(
        affected_user_id=affected_user_id,
        actor_user_id=actor_user_id,
        action=action,
        ip_address=ip or meta["ip"],
        user_agent=user_agent or meta["user_agent"],
        extra=extra,
    )
    db.add(row)
    db.flush()
    logger.info(
        "gdpr_event action=%s user=%s actor=%s",
        action,
        affected_user_id,
        actor_user_id,
    )
    return row
