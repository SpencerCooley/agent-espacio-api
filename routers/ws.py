"""
WebSocket router for real-time events.

Provides a single WebSocket endpoint that:
1. Authenticates the client via Bearer token or API key
2. Resolves folder scope at connection time
3. Validates subscriptions against scope (rejects out-of-scope channels)
4. Filters broadcasts by scope before delivery

Usage:
  ws://api/ws/events

  Connect, then send:
  {"action": "auth", "token": "<bearer>"}
  {"action": "auth", "api_key": "<agent-key>"}
  {"action": "subscribe", "channel": "folder:{folder_id}"}
  {"action": "subscribe", "channel": "global"}
  {"action": "unsubscribe", "channel": "folder:{folder_id}"}
"""
import json
import os
import asyncio
import threading
from dataclasses import dataclass, field
from uuid import UUID
from typing import Dict, Set, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from dependencies.dependencies import get_ws_auth, hash_api_key
from services import events
from models.user import User
from models.api_key import APIKey
from models.artifact import Artifact
from services.permissions import (
    Scope,
    AuthContext,
    resolve_scope,
    folder_id_in_scope,
    artifact_in_scope,
    get_scope_folder_ids,
)

# Create a sync engine for WebSocket auth (since get_db is async generator)
DATABASE_URL = os.environ.get('DATABASE_URL',
    'postgresql://agentespacio:agentespacio@db:5432/agentespacio_db')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

router = APIRouter(
    prefix="/ws",
    tags=["WebSocket"],
)


@dataclass
class ConnectionState:
    """WebSocket connection state including auth principal and resolved scope."""
    scope: Scope
    user: Optional[User] = None
    api_key: Optional[APIKey] = None
    scope_folder_ids: Optional[Set[UUID]] = None  # None = unrestricted
    channels: Set[str] = field(default_factory=set)


# Active connections: websocket -> connection state
_connections: Dict[WebSocket, ConnectionState] = {}
_connections_lock = threading.Lock()

# Cached event loop for broadcasting from background thread
_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_loop() -> Optional[asyncio.AbstractEventLoop]:
    """Get the running event loop, caching it for thread-safe access."""
    global _loop
    if _loop is not None and not _loop.is_closed():
        return _loop
    try:
        _loop = asyncio.get_event_loop()
    except Exception as e:
        print(f"[WS] get_loop error: {e}", flush=True)
        return None
    return _loop


def _get_channels(event: dict) -> list[str]:
    """
    Determine the channels an event should be broadcast to.

    For move events, broadcasts to both source and destination folders.
    Deploy events also go to artifact:{id}.
    For other events, returns the single folder channel or 'global'.
    """
    channels = []
    folder_id = event.get("folder_id")
    if folder_id:
        channels.append(f"folder:{folder_id}")
    payload = event.get("payload", {})
    source_folder_id = payload.get("source_folder_id")
    if source_folder_id and source_folder_id != folder_id:
        channels.append(f"folder:{source_folder_id}")
    # Artifact-scoped events (deploy status, etc.)
    resource_id = event.get("resource_id")
    event_type = event.get("event_type") or ""
    if resource_id and (
        event_type.startswith("artifact.deploy")
        or event_type.startswith("artifact.")
    ):
        channels.append(f"artifact:{resource_id}")
    if not channels:
        channels.append("global")
    return channels


def _event_in_scope(state: ConnectionState, event: dict) -> bool:
    """
    Check if an event is within the connection's folder scope.
    For move events, allows if either source or destination is in scope.
    """
    if state.scope.is_unrestricted:
        return True
    folder_id = event.get("folder_id")
    source_folder_id = event.get("payload", {}).get("source_folder_id")
    for fid in (folder_id, source_folder_id):
        if fid:
            try:
                uuid_fid = UUID(fid)
                if state.scope_folder_ids and uuid_fid in state.scope_folder_ids:
                    return True
            except ValueError:
                pass
    return False


def _can_subscribe(db: Session, state: ConnectionState, channel: str) -> bool:
    """
    Validate whether a connection is allowed to subscribe to a channel.
    Strict scope check (no embed-read exception) for both folder and artifact channels.
    """
    if state.scope.is_unrestricted:
        return True
    if channel == "global":
        return True
    if channel.startswith("folder:"):
        folder_id_str = channel.split(":", 1)[1]
        try:
            folder_id = UUID(folder_id_str)
        except ValueError:
            return False
        return folder_id_in_scope(db, state.scope, folder_id)
    if channel.startswith("artifact:"):
        artifact_id_str = channel.split(":", 1)[1]
        try:
            artifact_id = UUID(artifact_id_str)
        except ValueError:
            return False
        artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
        if not artifact:
            return False
        return artifact_in_scope(db, state.scope, artifact)
    return True


def _broadcast_event(event: dict) -> None:
    """
    Broadcast an event to scoped WebSocket connections subscribed to its channels.

    Each event is first checked against the connection's resolved folder scope.
    Move events are delivered if either source or destination is in scope.
    """
    target_channels = _get_channels(event)
    print(f"[WS] Broadcasting event {event.get('event_type')} to channels {target_channels}")
    if not target_channels:
        return

    message = json.dumps(event)
    loop = _get_loop()
    if not loop:
        print("[WS] No event loop available, skipping broadcast")
        return

    with _connections_lock:
        connections = list(_connections.items())

    print(f"[WS] {len(connections)} connections, sending to matching channels")
    for ws, state in connections:
        # Scope filter: drop events for out-of-scope folders
        if not _event_in_scope(state, event):
            continue

        # Channel filter: client must be subscribed to a target channel or global
        should_send = "global" in state.channels
        if not should_send:
            for tc in target_channels:
                if tc in state.channels:
                    should_send = True
                    break

        if should_send:
            try:
                asyncio.run_coroutine_threadsafe(ws.send_text(message), loop)
                print(f"[WS] Sent to connection with channels: {state.channels}")
            except Exception as e:
                print(f"[WS] Send error: {e}")
                pass


# Subscribe to the event bus on module load
events.subscribe(_broadcast_event)


@router.websocket("/events")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time events.

    Auth flow:
      1. Client connects
      2. Server accepts connection
      3. Client sends: {"action": "auth", "token": "..."} or {"action": "auth", "api_key": "..."}
      4. Server validates, resolves scope, and allows subscriptions

    Messages (client -> server):
      {"action": "auth", "token": "..."}
      {"action": "auth", "api_key": "..."}
      {"action": "subscribe", "channel": "folder:{folder_id}"}
      {"action": "subscribe", "channel": "global"}
      {"action": "unsubscribe", "channel": "folder:{folder_id}"}

    Messages (server -> client):
      {"event_type": "folder.created", "folder_id": "...", "resource_id": "...", ...}
      {"action": "subscribe_denied", "channel": "...", "reason": "out of scope"}
    """
    print("[WS] Connection received")
    await websocket.accept()
    print("[WS] Connection accepted")

    # Wait for auth message
    state: Optional[ConnectionState] = None
    try:
        data = await websocket.receive_text()
        print(f"[WS] Received message: {data[:100]}")
        message = json.loads(data)
        if message.get("action") == "auth":
            token = message.get("token")
            api_key_str = message.get("api_key")
            db = SessionLocal()
            try:
                user: Optional[User] = None
                api_key: Optional[APIKey] = None

                if token:
                    user = get_ws_auth(token, db)
                elif api_key_str:
                    key_hash = hash_api_key(api_key_str)
                    api_key = db.query(APIKey).filter(
                        APIKey.key_hash == key_hash,
                        APIKey.is_active == True
                    ).first()
                    if api_key and api_key.user_id:
                        user = db.query(User).filter(User.id == api_key.user_id).first()

                if user or api_key:
                    ctx = AuthContext(user=user, api_key=api_key)
                    scope = resolve_scope(db, ctx)
                    scope_folder_ids = get_scope_folder_ids(db, scope) if not scope.is_unrestricted else None
                    state = ConnectionState(
                        user=user,
                        api_key=api_key,
                        scope=scope,
                        scope_folder_ids=scope_folder_ids,
                    )
                    with _connections_lock:
                        _connections[websocket] = state
                    print(f"[WS] Auth successful for {'user: ' + user.email if user else 'agent'}")
                else:
                    print("[WS] Auth failed: no valid token or api key")
            finally:
                db.close()
    except Exception as e:
        print(f"[WS] Auth error: {e}")
        pass

    if state is None:
        print("[WS] Closing connection: not authenticated")
        try:
            await websocket.close(code=1008, reason="Authentication required")
        except Exception:
            pass
        return

    print(f"[WS] Connection added, total connections: {len(_connections)}")

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                action = message.get("action")
                channel = message.get("channel")

                if action == "subscribe" and channel:
                    db = SessionLocal()
                    try:
                        if _can_subscribe(db, state, channel):
                            state.channels.add(channel)
                            print(f"[WS] Subscribed to {channel}, channels: {state.channels}")
                        else:
                            print(f"[WS] Subscription denied for {channel}")
                            await websocket.send_json({
                                "action": "subscribe_denied",
                                "channel": channel,
                                "reason": "out of scope"
                            })
                    finally:
                        db.close()
                elif action == "unsubscribe" and channel:
                    state.channels.discard(channel)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        with _connections_lock:
            _connections.pop(websocket, None)
        print(f"[WS] Connection removed, total connections: {len(_connections)}")
