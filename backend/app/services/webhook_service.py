"""Webhook event dispatcher.

Usage::

    from app.services.webhook_service import emit_event

    emit_event(db, project_id=project.id, event="task.created",
               data={"task": task_out.model_dump()})

This synchronously writes a ``WebhookDelivery`` row for every
matching active subscription.  The actual HTTP POST is done by the
periodic ``webhook_dispatch_job`` (Celery beat).  We never block
the caller on outbound HTTP.

Supported events:

* ``task.created``
* ``task.moved``  (``data.to_status`` / ``data.from_status``)
* ``task.assigned``
* ``task.completed``
* ``meeting.uploaded``
* ``meeting.processed``
* ``member.joined``
* ``digest.sent``
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.webhook import WebhookDelivery, WebhookSubscription


logger = logging.getLogger(__name__)


ALL_EVENTS: List[str] = [
    "task.created",
    "task.moved",
    "task.assigned",
    "task.completed",
    "meeting.uploaded",
    "meeting.processed",
    "member.joined",
    "digest.sent",
]


def generate_secret() -> str:
    return secrets.token_hex(32)


def emit_event(
    db: Session,
    *,
    project_id: str,
    event: str,
    data: Dict[str, Any],
) -> List[WebhookDelivery]:
    """Enqueue an event for every active subscription that wants it.

    Returns the list of ``WebhookDelivery`` rows that were created.
    Idempotent: each call creates a new row, so a retry from the
    caller creates a new attempt.
    """
    subs: List[WebhookSubscription] = (
        db.query(WebhookSubscription)
        .filter(
            WebhookSubscription.project_id == project_id,
            WebhookSubscription.is_active.is_(True),
        )
        .all()
    )
    rows: List[WebhookDelivery] = []
    for sub in subs:
        if sub.events and event not in sub.events:
            continue
        delivery = WebhookDelivery(
            subscription_id=sub.id,
            event=event,
            payload={
                "event": event,
                "project_id": project_id,
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "data": data,
            },
        )
        db.add(delivery)
        rows.append(delivery)
    if rows:
        db.flush()
        logger.info(
            "emit_event: event=%s project=%s → %d delivery row(s)",
            event,
            project_id,
            len(rows),
        )
    return rows


def serialize_payload(delivery: WebhookDelivery) -> str:
    return json.dumps(delivery.payload, default=str, separators=(",", ":"))
