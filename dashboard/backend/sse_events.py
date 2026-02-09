#!/usr/bin/env python3
"""
SSE (Server-Sent Events) implementation for real-time dashboard updates

Streams new API calls to connected clients as they happen.

Usage:
    from sse_events import SSEManager, broadcast_event

    # Broadcast new API call to all connected clients
    broadcast_event({
        "type": "api_call",
        "data": {...}
    })
"""

import json
import time
import threading
from queue import Queue, Empty
from typing import Dict, Set, Any, Optional
from datetime import datetime


# ============================================================================
# SSE MANAGER - Manages client connections and broadcasts
# ============================================================================
class SSEManager:
    """Manages SSE client connections and event broadcasting"""

    def __init__(self):
        self._clients: Dict[str, Queue] = {}
        self._lock = threading.Lock()
        self._running = True

    def add_client(self, client_id: str, queue: Queue) -> None:
        """Add a new client connection"""
        with self._lock:
            self._clients[client_id] = queue
            print(f"[SSE] Client connected: {client_id} (total: {len(self._clients)})")

    def remove_client(self, client_id: str) -> None:
        """Remove a client connection"""
        with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]
                print(f"[SSE] Client disconnected: {client_id} (total: {len(self._clients)})")

    def broadcast(self, event: Dict[str, Any]) -> None:
        """Broadcast event to all connected clients"""
        if not self._clients:
            return

        event_data = json.dumps(event)
        dead_clients = []

        with self._lock:
            for client_id, queue in self._clients.items():
                try:
                    # Non-blocking put with timeout
                    queue.put_nowait(event_data)
                except:
                    # Queue full or client dead
                    dead_clients.append(client_id)

        # Clean up dead clients
        for client_id in dead_clients:
            self.remove_client(client_id)

    def get_client_count(self) -> int:
        """Get number of connected clients"""
        with self._lock:
            return len(self._clients)

    def shutdown(self) -> None:
        """Shutdown the SSE manager"""
        self._running = False
        with self._lock:
            self._clients.clear()


# Global SSE manager instance
_sse_manager = SSEManager()


def get_sse_manager() -> SSEManager:
    """Get the global SSE manager instance"""
    return _sse_manager


def broadcast_event(event_type: str, data: Dict[str, Any]) -> None:
    """
    Broadcast an event to all connected SSE clients

    Args:
        event_type: Type of event ('api_call', 'alert', 'gateway_status', etc.)
        data: Event data payload
    """
    event = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    _sse_manager.broadcast(event)


def broadcast_api_call(call_data: Dict[str, Any]) -> None:
    """Broadcast a new API call event"""
    broadcast_event("api_call", call_data)


def broadcast_alert(alert_data: Dict[str, Any]) -> None:
    """Broadcast a budget alert event"""
    broadcast_event("alert", alert_data)


def broadcast_gateway_status(status_data: Dict[str, Any]) -> None:
    """Broadcast gateway status change"""
    broadcast_event("gateway_status", status_data)


# ============================================================================
# SSE RESPONSE FORMATTING
# ============================================================================
def format_sse_line(event_type: str, data: str) -> bytes:
    """Format an SSE event line"""
    return f"event: {event_type}\ndata: {data}\n\n".encode('utf-8')


def format_sse_keepalive() -> bytes:
    """Format an SSE keepalive comment (prevents timeout)"""
    return b":keepalive\n\n"


# ============================================================================
# CLIENT QUEUE GENERATOR
# ============================================================================
def client_event_generator(client_id: str, queue: Queue):
    """
    Generator function that yields SSE events for a client

    Args:
        client_id: Unique client identifier
        queue: Queue for receiving events

    Yields:
        Formatted SSE event bytes
    """
    manager = get_sse_manager()

    try:
        # Send initial connection event
        yield format_sse_line("connected", json.dumps({
            "client_id": client_id,
            "timestamp": datetime.now().isoformat()
        }))

        while manager._running:
            try:
                # Wait for event with 30s timeout
                event_data = queue.get(timeout=30)
                yield format_sse_line("update", event_data)
            except Empty:
                # Send keepalive on timeout
                yield format_sse_keepalive()

    except GeneratorExit:
        # Client disconnected
        manager.remove_client(client_id)
    except Exception as e:
        print(f"[SSE] Error for client {client_id}: {e}")
        manager.remove_client(client_id)


# ============================================================================
# CLIENT ID GENERATION
# ============================================================================
import uuid

def generate_client_id() -> str:
    """Generate a unique client ID"""
    return str(uuid.uuid4())
