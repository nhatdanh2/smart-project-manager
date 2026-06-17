"""Device push tokens (Expo push) + send helper.

Devices POST their ``ExponentPushToken[...]`` here, and any
backend code can call :func:`send_to_user` to dispatch a push.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable, Optional

from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


logger = logging.getLogger(__name__)


def _uuid() -> str:
    import uuid as _u
    return str(_u.uuid4())


class PushDevice(Base):
    __tablename__ = "push_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    platform: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    device_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PushDeviceIn(BaseModel):
    token: str
    platform: Optional[str] = None
    device_name: Optional[str] = None
