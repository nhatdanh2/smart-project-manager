"""Kick stale members out of a project's presence map.

Run every 30 seconds via Celery beat.  A member is considered
stale if their ``last_seen`` is older than the grace period
(45 seconds by default — matches the heartbeat interval used by
``PresenceAvatars`` on the frontend).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict

from app.database import SessionLocal
from app.services.realtime import broadcast_sync


logger = logging.getLogger(__name__)


STALE_AFTER_SECONDS = 45


def kick_stale_presence() -> int:
    """Remove stale entries from the in-memory presence map.

    Returns the number of projects that had at least one member
    kicked.
    """
    from app.services.realtime import presence  # local import avoids cycles

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_AFTER_SECONDS)
        kicked_total = 0
        # ``presence`` is keyed by project_id → { user_id: { name, last_seen } }
        snapshot: Dict[str, Dict[str, dict]] = {pid: dict(m) for pid, m in presence.items()}
        for project_id, members in snapshot.items():
            before = len(members)
            for uid, info in list(members.items()):
                last = info.get("last_seen")
                if isinstance(last, str):
                    try:
                        last = datetime.fromisoformat(last)
                    except Exception:
                        continue
                if last is None:
                    continue
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                if last < cutoff:
                    members.pop(uid, None)
                    logger.info(
                        "presence_cleanup: kicked user=%s from project=%s",
                        uid,
                        project_id,
                    )
            if len(members) < before:
                kicked_total += 1
                # Persist the cleaned map back + broadcast
                presence[project_id] = members
                broadcast_sync(
                    project_id,
                    {
                        "type": "presence",
                        "members": [
                            {"userId": uid, "name": m.get("name", "")}
                            for uid, m in members.items()
                        ],
                    },
                )
        return kicked_total
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    print(kick_stale_presence())
