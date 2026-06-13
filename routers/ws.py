"""
WebSocket router for real-time events.

Provides a single WebSocket endpoint that:
1. Authenticates the client via Bearer token
2. Allows clients to subscribe to channels (e.g., 'folder:{id}', 'global')
3. Listens to the event bus and fans out messages to subscribed clients

Usage:
  ws://api/ws/events
  
  Connect, then send:
  {"action": "subscribe", "channel": "folder:{folder_id}"}
  {"action": "subscribe", "channel": "global"}
  {"action": "unsubscribe", "channel": "folder:{folder_id}"}
"""
import json
import os
import asyncio
import threading
from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from dependencies.dependencies import get_ws_auth
from services import events

# Create a sync engine for WebSocket auth (since get_db is async generator)
DATABASE_URL = os.environ.get('DATABASE_URL', 
    'postgresql://agentespacio:agentespacio@db:5432/agentespacio_db')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

router = APIRouter(
    prefix="/ws",
    tags=["WebSocket"],
)

# Active connections: websocket -> set of subscribed channels
_connections: Dict[WebSocket, Set[str]] = {}
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
    if not channels:
        channels.append("global")
    return channels


def _broadcast_event(event: dict) -> None:
    """
    Broadcast an event to all WebSocket connections subscribed to its channels.
    
    For move events, broadcasts to both source and destination folder channels.
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
    for ws, client_channels in connections:
        # Send if client is subscribed to any of the target channels or global
        should_send = "global" in client_channels
        if not should_send:
            for tc in target_channels:
                if tc in client_channels:
                    should_send = True
                    break
        if should_send:
            try:
                asyncio.run_coroutine_threadsafe(ws.send_text(message), loop)
                print(f"[WS] Sent to connection with channels: {client_channels}")
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
      3. Client sends: {"action": "auth", "token": "..."}
      4. Server validates and allows subscriptions
    
    Messages (client -> server):
      {"action": "auth", "token": "..."}
      {"action": "subscribe", "channel": "folder:{folder_id}"}
      {"action": "subscribe", "channel": "global"}
      {"action": "unsubscribe", "channel": "folder:{folder_id}"}
    
    Messages (server -> client):
      {"event_type": "folder.created", "folder_id": "...", "resource_id": "...", ...}
    """
    print("[WS] Connection received")
    await websocket.accept()
    print("[WS] Connection accepted")

    # Wait for auth message
    authenticated = False
    try:
        data = await websocket.receive_text()
        print(f"[WS] Received message: {data[:100]}")
        message = json.loads(data)
        if message.get("action") == "auth":
            token = message.get("token")
            db = SessionLocal()
            try:
                user = get_ws_auth(token, db)
                if user:
                    authenticated = True
                    print(f"[WS] Auth successful for user: {user.email}")
                else:
                    print(f"[WS] Auth failed: invalid token")
            finally:
                db.close()
    except Exception as e:
        print(f"[WS] Auth error: {e}")
        pass

    if not authenticated:
        print("[WS] Closing connection: not authenticated")
        try:
            await websocket.close(code=1008, reason="Authentication required")
        except Exception:
            pass
        return
    
    with _connections_lock:
        _connections[websocket] = set()
    print(f"[WS] Connection added, total connections: {len(_connections)}")
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                action = message.get("action")
                channel = message.get("channel")
                
                with _connections_lock:
                    if action == "subscribe" and channel:
                        _connections[websocket].add(channel)
                        print(f"[WS] Subscribed to {channel}, channels: {_connections[websocket]}")
                    elif action == "unsubscribe" and channel:
                        _connections[websocket].discard(channel)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        with _connections_lock:
            _connections.pop(websocket, None)
        print(f"[WS] Connection removed, total connections: {len(_connections)}")
