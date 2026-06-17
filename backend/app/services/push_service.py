"""Expo push notification helper.

Wraps the official ``expo-server-sdk`` for sending pushes.  In
dev (no Expo credentials) we degrade to a no-op so the API keeps
working.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.push import PushDevice


logger = logging.getLogger(__name__)


def _client():
    try:
        from exponent_server_sdk import (
            DeviceNotRegisteredError,
            PushClient,
            PushMessage,
        )
    except ImportError:
        return None, None
    return PushClient(), (DeviceNotRegisteredError,)


def _build_messages(
    tokens: List[str], title: str, body: str, data: Optional[Dict[str, Any]] = None
):
    from exponent_server_sdk import PushMessage

    return [
        PushMessage(
            to=t,
            title=title,
            body=body,
            data=data or {},
            sound="default",
            priority="high",
        )
        for t in tokens
    ]


def send_to_user(
    db: Session,
    user_id: str,
    *,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
) -> int:
    """Send a push to every device the user has registered.

    Returns the number of devices we tried to reach.  Failures are
    logged and the offending device is unregistered so we don't
    keep retrying.
    """
    client, exc_classes = _client()
    if client is None:
        logger.warning("expo-server-sdk not installed; push skipped")
        return 0

    devices: Iterable[PushDevice] = (
        db.query(PushDevice).filter(PushDevice.user_id == user_id).all()
    )
    tokens = [d.token for d in devices]
    if not tokens:
        return 0

    messages = _build_messages(tokens, title, body, data)
    delivered = 0
    for token, resp in client.publish_multiple(messages):
        try:
            resp.validate_response()
            delivered += 1
        except Exception as exc:  # noqa: BLE001
            # If the device unregistered, drop the row
            if exc_classes and isinstance(exc, exc_classes[0]):
                db.query(PushDevice).filter(PushDevice.token == token).delete()
            else:
                logger.warning("push delivery failed for %s: %s", token, exc)
    db.commit()
    return delivered
