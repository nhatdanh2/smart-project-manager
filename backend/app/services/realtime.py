"""Realtime helper.

Phase 1 ships a simple in-process pub/sub keyed by project id.  Each
project gets a ``set`` of asyncio.Queue subscribers; broadcasts push
to all of them.  When Celery/Redis is wired up, this can be swapped for
Redis pub/sub without touching call sites.

Phase 4 also tracks per-user subscriptions for cross-project
notifications (the bell UI uses these).
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Dict, Set


class _Hub:
    def __init__(self) -> None:
        self._subs: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        # user_id -> set of queues that want user-scoped events (bell UI)
        self._user_subs: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        # which project_ids each user has joined (for fan-out of project
        # events to the bell UI).  We don't fan-out project events to
        # users right now - only explicit notifications go user-side.
        self._user_projects: Dict[str, Set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, project_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=128)
        async with self._lock:
            self._subs[project_id].add(q)
        return q

    async def unsubscribe(self, project_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            self._subs.get(project_id, set()).discard(q)

    async def broadcast(self, project_id: str, event: Dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._subs.get(project_id, set()))
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    pass

    async def subscribe_user(self, user_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        async with self._lock:
            self._user_subs[user_id].add(q)
        return q

    async def unsubscribe_user(self, user_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            self._user_subs.get(user_id, set()).discard(q)

    def push_to_user(self, user_id: str, event: Dict[str, Any]) -> None:
        """Schedule a push to all user-scoped queues (sync, fire-and-forget)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._broadcast_user(user_id, event))

    async def _broadcast_user(self, user_id: str, event: Dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._user_subs.get(user_id, set()))
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    pass


hub = _Hub()


def get_hub() -> _Hub:
    """Return the singleton hub.  Useful for services that just need to push."""
    return hub


def broadcast_sync(project_id: str, event: Dict[str, Any]) -> None:
    """Schedule a broadcast from sync code.  Safe to call from request handlers."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(hub.broadcast(project_id, event))
