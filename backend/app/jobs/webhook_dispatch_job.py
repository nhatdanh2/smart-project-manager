"""Outbound webhook delivery.

Tries to deliver every ``pending`` ``WebhookDelivery`` whose
``next_retry_at`` is due.  Backoff schedule:

* attempt 1 → immediate
* attempt 2 → +1 minute
* attempt 3 → +5 minutes
* attempt 4 → +30 minutes
* attempt 5+ → "dead" (sent to dead-letter; surfaces in the UI)

Successful delivery is HTTP 2xx.  Network errors and 5xx are
retried.  4xx (other than 408/429) is treated as permanent — the
client rejected the payload, no point retrying.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.webhook import WebhookDelivery, WebhookSubscription


logger = logging.getLogger(__name__)


MAX_ATTEMPTS = 5
RETRY_BACKOFF_SECONDS = [0, 60, 5 * 60, 30 * 60]
# 4xx codes that ARE retryable
RETRYABLE_4XX = {408, 425, 429}


def _sign(body: str, secret: str) -> str:
    mac = hmac.new(secret.encode(), body.encode(), hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def _format_for_target(target: str, payload: dict) -> dict:
    """Translate our generic event payload to the target's flavour.

    Slack and Discord both expect a ``text`` field (Discord calls
    it ``content``).  We forward the title as the main line and
    include the data in an ``attachments``/``embeds`` block.
    """
    if target == "slack":
        text = payload["data"].get("text") or payload["event"].replace(".", " ").title()
        return {
            "text": text,
            "attachments": [
                {
                    "color": "#0ea5e9",
                    "fields": [
                        {"title": "Project", "value": payload.get("project_id", ""), "short": True},
                        {"title": "Event", "value": payload["event"], "short": True},
                    ],
                    "text": json.dumps(payload["data"], default=str)[:2000],
                }
            ],
        }
    if target == "discord":
        return {
            "content": payload["data"].get("text")
            or payload["event"].replace(".", " ").title(),
            "embeds": [
                {
                    "title": payload["event"],
                    "description": json.dumps(payload["data"], default=str)[:2000],
                    "color": 0x0EA5E9,
                }
            ],
        }
    return payload


def _is_retryable(status: int) -> bool:
    if 200 <= status < 300:
        return False
    if status in RETRYABLE_4XX or 500 <= status < 600:
        return True
    return False


def _next_retry(attempts: int) -> Optional[datetime]:
    if attempts >= len(RETRY_BACKOFF_SECONDS):
        return None  # past the schedule → dead-letter
    return datetime.now(timezone.utc) + timedelta(seconds=RETRY_BACKOFF_SECONDS[attempts])


async def _deliver_one(
    client: httpx.AsyncClient, delivery: WebhookDelivery, sub: WebhookSubscription
) -> None:
    body = json.dumps(delivery.payload, default=str, separators=(",", ":"))
    target_payload = _format_for_target(sub.target, delivery.payload)
    body_out = json.dumps(target_payload, default=str, separators=(",", ":"))
    signature = _sign(body_out, sub.secret)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SmartPM-Webhook/1.0",
        "X-SmartPM-Event": delivery.event,
        "X-SmartPM-Delivery-Id": delivery.id,
        "X-SmartPM-Signature": signature,
    }
    delivery.attempts += 1
    try:
        resp = await client.post(sub.url, content=body_out, headers=headers, timeout=10.0)
        delivery.last_status_code = resp.status_code
        delivery.last_response = (resp.text or "")[:1000]
        if 200 <= resp.status_code < 300:
            delivery.status = "delivered"
            delivery.next_retry_at = None
        elif _is_retryable(resp.status_code):
            delivery.status = "pending"
            delivery.next_retry_at = _next_retry(delivery.attempts)
            if delivery.next_retry_at is None:
                delivery.status = "dead"
        else:
            # permanent
            delivery.status = "failed"
            delivery.next_retry_at = None
    except Exception as exc:  # noqa: BLE001
        delivery.last_status_code = None
        delivery.last_response = repr(exc)[:1000]
        delivery.next_retry_at = _next_retry(delivery.attempts)
        if delivery.next_retry_at is None:
            delivery.status = "dead"
        else:
            delivery.status = "pending"


def deliver_pending(limit: int = 50) -> dict:
    """Process up to ``limit`` pending deliveries.  Returns counts."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        pending = (
            db.query(WebhookDelivery)
            .filter(
                WebhookDelivery.status == "pending",
            )
            .order_by(WebhookDelivery.created_at)
            .limit(limit * 4)  # over-fetch so we can skip not-yet-due
            .all()
        )
        due = [
            d for d in pending
            if d.next_retry_at is None or d.next_retry_at <= now
        ][:limit]
        if not due:
            return {"delivered": 0, "failed": 0, "dead": 0, "remaining": 0}

        subs_by_id = {
            s.id: s
            for s in db.query(WebhookSubscription)
            .filter(WebhookSubscription.id.in_([d.subscription_id for d in due]))
            .all()
        }

        async def _runner():
            async with httpx.AsyncClient() as client:
                for delivery in due:
                    sub = subs_by_id.get(delivery.subscription_id)
                    if not sub or not sub.is_active:
                        delivery.status = "failed"
                        delivery.last_response = "subscription disabled"
                        continue
                    await _deliver_one(client, delivery, sub)

        asyncio.run(_runner())

        delivered = sum(1 for d in due if d.status == "delivered")
        failed = sum(1 for d in due if d.status == "failed")
        dead = sum(1 for d in due if d.status == "dead")
        db.commit()
        remaining = (
            db.query(WebhookDelivery).filter(WebhookDelivery.status == "pending").count()
        )
        logger.info(
            "webhook_delivery: delivered=%d failed=%d dead=%d remaining=%d",
            delivered,
            failed,
            dead,
            remaining,
        )
        return {
            "delivered": delivered,
            "failed": failed,
            "dead": dead,
            "remaining": remaining,
        }
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    print(deliver_pending())
