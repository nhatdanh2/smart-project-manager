"""Audit log of GDPR-relevant events (data exports, deletions, admin recovery)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class GDPRAuditLog(Base):
    __tablename__ = "gdpr_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # user_id of the affected user.  We keep this even after the user
    # is purged so admins can answer "what happened to account X".
    affected_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # user_id of the actor (usually the affected user themselves).
    actor_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )
    # "export.requested", "export.completed", "delete.requested",
    # "delete.cancelled", "delete.purged", "admin.recover"
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
