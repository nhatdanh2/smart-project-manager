"""Project presence tracker.

Tracks which users are currently online in which projects.  In-process
state keyed by ``(project_id, user_id)`` with a TTL of 90s.  A user
is considered present if they have a live WebSocket subscription to
``/ws/projects/{id}`` (or a recent heartbeat).

The list is broadcast on every change so connected clients can render
avatars in real time.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional

from app.services.realtime import hub


logger = logging.getLogger(__name__)

# How long (seconds) since the last heartbeat before we consider a user offline
PRESENCE_TTL = 90.0

# project_id -> user_id -> {name, last_seen}
_state: Dict[str, Dict[str, Dict[str, float]]] = {}
_lock: Optional[asyncio.Lock] = None


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


def _now() -> float:
    return time.time()


async def heartbeat(project_id: str, user_id: str, name: str) -> None:
    """Record a presence heartbeat for a user in a project."""
    async with _get_lock():
        bucket = _state.setdefault(project_id, {})
        prev = bucket.get(user_id)
        if not prev or prev.get("name") != name:
            bucket[user_id] = {"name": name, "last_seen": _now()}
            await _broadcast(project_id, await snapshot_locked(project_id))
        else:
            prev["last_seen"] = _now()
            prev["name"] = name


async def leave(project_id: str, user_id: str) -> None:
    """Remove a user from a project presence bucket."""
    async with _get_lock():
        bucket = _state.get(project_id)
        if not bucket:
            return
        if user_id in bucket:
            del bucket[user_id]
            await _broadcast(project_id, await snapshot_locked(project_id))


async def snapshot_locked(project_id: str) -> List[Dict]:
    """Return the current presence list, pruning stale entries."""
    bucket = _state.get(project_id, {})
    now = _now()
    stale = [
        uid
        for uid, data in bucket.items()
        if now - data.get("last_seen", 0) > PRESENCE_TTL
    ]
    for uid in stale:
        del bucket[uid]
    return [
        {"userId": uid, "name": data["name"], "lastSeen": data["last_seen"]}
        for uid, data in bucket.items()
    ]


async def snapshot(project_id: str) -> List[Dict]:
    async with _get_lock():
        return await snapshot_locked(project_id)


async def _broadcast(project_id: str, members: List[Dict]) -> None:
    """Push the current presence list to all subscribers of the project."""
    try:
        await hub.broadcast(
            project_id,
            {"type": "presence", "members": members, "ts": _now()},
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("presence broadcast failed: %s", exc)


def snapshot_sync(project_id: str) -> List[Dict]:
    """Synchronous snapshot for the REST endpoint."""
    bucket = _state.get(project_id, {})
    now = _now()
    out: List[Dict] = []
    for uid, data in list(bucket.items()):
        if now - data.get("last_seen", 0) > PRESENCE_TTL:
            del bucket[uid]
            continue
        out.append(
            {"userId": uid, "name": data["name"], "lastSeen": data["last_seen"]}
        )
    return out
