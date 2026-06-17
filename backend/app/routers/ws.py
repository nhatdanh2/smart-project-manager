"""WebSocket router - per-project + per-user realtime channels.

Phase 6 also includes presence broadcasting: when a user joins a
project WS we announce them via ``presence`` events; when they leave
(WS disconnect or TTL elapses) we remove them.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.services.auth_service import decode_token
from app.services.presence_service import (
    heartbeat as presence_heartbeat,
    leave as presence_leave,
    snapshot as presence_snapshot_async,
    snapshot_sync as presence_snapshot_sync,
)
from app.services.realtime import hub

# Re-import WebSocket for type hints / runtime
from fastapi.websockets import WebSocket, WebSocketDisconnect


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["ws"])


def _authenticate_token(token: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (user_id, user_name) or (None, None)."""
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None, None
        return payload.get("sub"), payload.get("name")
    except Exception:
        return None, None


async def _authenticate(websocket: WebSocket, token: str) -> Tuple[Optional[str], Optional[str]]:
    user_id, name = _authenticate_token(token)
    if not user_id:
        await websocket.close(code=4401)
    return user_id, name


@router.websocket("/projects/{project_id}")
async def project_ws(
    websocket: WebSocket,
    project_id: str,
    token: str = Query(...),
) -> None:
    user_id, name = await _authenticate(websocket, token)
    if not user_id:
        return
    await websocket.accept()
    q = await hub.subscribe(project_id)
    # Register presence and broadcast the new list
    try:
        await presence_heartbeat(project_id, user_id, name or "User")
    except Exception:
        pass
    try:
        await websocket.send_json(
            {"type": "hello", "projectId": project_id, "userId": user_id}
        )
        # Send the current presence snapshot right away so the joining
        # user doesn't have to wait for the next change event.
        snapshot = await presence_snapshot_async(project_id)
        await websocket.send_json(
            {"type": "presence", "members": snapshot, "ts": time.time()}
        )
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if msg == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg == "presence":
                    try:
                        await presence_heartbeat(project_id, user_id, name or "User")
                        snapshot = await presence_snapshot_async(project_id)
                        await websocket.send_json(
                            {"type": "presence", "members": snapshot, "ts": time.time()}
                        )
                    except Exception:
                        pass
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
                # Heartbeat so presence TTL is refreshed
                try:
                    await presence_heartbeat(project_id, user_id, name or "User")
                except Exception:
                    pass
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("WS error: %s", exc)
    finally:
        try:
            await presence_leave(project_id, user_id)
        except Exception:
            pass
        await hub.unsubscribe(project_id, q)


@router.websocket("/me")
async def user_ws(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    """Per-user channel — used by the notification bell."""
    user_id, _ = await _authenticate(websocket, token)
    if not user_id:
        return
    await websocket.accept()
    q = await hub.subscribe_user(user_id)
    try:
        await websocket.send_json({"type": "hello", "userId": user_id})
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if msg == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("WS error: %s", exc)
    finally:
        await hub.unsubscribe_user(user_id, q)


# --- REST: presence snapshot ---


class PresenceMember(BaseModel):
    userId: str
    name: str
    lastSeen: float


class PresenceOut(BaseModel):
    members: List[PresenceMember]


@router.get("/projects/{project_id}/presence", response_model=PresenceOut)
def get_presence(
    project_id: str,
    token: str = Query(...),
) -> PresenceOut:
    """Read-only snapshot of who's currently online in this project."""
    user_id, _ = _authenticate_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    members = presence_snapshot_sync(project_id)
    return PresenceOut(members=[PresenceMember(**m) for m in members])
