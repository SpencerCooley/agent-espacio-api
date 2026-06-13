"""
Central Event Bus for real-time notifications.

Uses Redis Pub/Sub to broadcast events across all API instances.
Controllers and routers call publish_event() after successful mutations.
The WebSocket router subscribes to events and fans them out to connected clients.
"""
import json
import os
import redis
import threading
from typing import Callable, Dict, List, Any
from datetime import datetime, timezone

# Redis connection
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

EVENT_CHANNEL = "agentespacio:events"

# In-memory subscribers (callbacks for WebSocket connections)
_subscribers: List[Callable[[Dict[str, Any]], None]] = []
_lock = threading.Lock()


def publish_event(
    event_type: str,
    folder_id: str,
    resource_id: str,
    payload: Dict[str, Any] = None,
    actor: Dict[str, Any] = None,
) -> None:
    """
    Publish an event to Redis Pub/Sub.
    
    Called from routers after successful mutations.
    
    Args:
        event_type: Type of event (e.g., 'folder.created', 'asset.deleted')
        folder_id: ID of the folder affected by the event
        resource_id: ID of the created/deleted/updated resource
        payload: Optional extra data (name, type, etc.)
        actor: Optional actor info (type, id, name)
    """
    event = {
        "event_type": event_type,
        "folder_id": folder_id,
        "resource_id": resource_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload or {},
        "actor": actor or {},
    }
    print(f"[EVENTS] Publishing {event_type} to {EVENT_CHANNEL}")
    try:
        result = redis_client.publish(EVENT_CHANNEL, json.dumps(event))
        print(f"[EVENTS] Publish result: {result} subscribers", flush=True)
    except Exception as e:
        print(f"[EVENTS] Publish failed: {e}", flush=True)


def subscribe(callback: Callable[[Dict[str, Any]], None]) -> None:
    """
    Subscribe to events.
    
    Args:
        callback: Function to call when an event is received
    """
    with _lock:
        if callback not in _subscribers:
            _subscribers.append(callback)


def unsubscribe(callback: Callable[[Dict[str, Any]], None]) -> None:
    """
    Unsubscribe from events.
    
    Args:
        callback: Function to remove from subscribers
    """
    with _lock:
        if callback in _subscribers:
            _subscribers.remove(callback)


def _dispatch_event(event: Dict[str, Any]) -> None:
    """
    Dispatch an event to all subscribers.
    """
    with _lock:
        subscriber_count = len(_subscribers)
    print(f"[EVENTS] Dispatching to {subscriber_count} subscribers")
    with _lock:
        for callback in list(_subscribers):
            try:
                callback(event)
            except Exception as e:
                print(f"[EVENTS] Callback error: {e}")
                pass


def _listen_for_events() -> None:
    """
    Background thread that listens to Redis Pub/Sub and dispatches events.
    """
    print("[EVENTS] Starting Redis listener thread", flush=True)
    try:
        # Create a fresh Redis client for this thread
        listener_client = redis.from_url(REDIS_URL, decode_responses=True)
        # Verify connectivity
        listener_client.ping()
        print("[EVENTS] Redis ping successful", flush=True)
    except Exception as e:
        print(f"[EVENTS] Redis connection failed: {e}", flush=True)
        return
    
    # Create pubsub in this thread (not thread-safe to share across threads)
    pubsub = listener_client.pubsub()
    pubsub.subscribe(EVENT_CHANNEL)
    print(f"[EVENTS] Subscribed to {EVENT_CHANNEL}", flush=True)
    
    # Use get_message with timeout instead of listen() to avoid blocking
    import time
    while True:
        message = pubsub.get_message(timeout=0.1)
        if message and message["type"] == "message":
            try:
                event = json.loads(message["data"])
                print(f"[EVENTS] Received event: {event.get('event_type')}", flush=True)
                _dispatch_event(event)
            except Exception as e:
                print(f"[EVENTS] Listener error: {e}", flush=True)
                pass
        elif message:
            print(f"[EVENTS] Non-message: {message['type']}", flush=True)
        time.sleep(0.1)


# Start background listener thread
def start_event_listener() -> None:
    """
    Start the background Redis Pub/Sub listener.
    Call this once on application startup.
    """
    print("[EVENTS] start_event_listener() called", flush=True)
    listener_thread = threading.Thread(target=_listen_for_events, daemon=True)
    listener_thread.start()
    print(f"[EVENTS] Listener thread started: {listener_thread.is_alive()}", flush=True)
