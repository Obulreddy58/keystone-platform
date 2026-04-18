"""
WebSocket hub for real-time updates.
Broadcasts events to all connected clients:
  - request_created: new infra request submitted
  - status_changed: request status updated (pipeline progress)
  - notification: targeted notification for a user
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

router = APIRouter()
logger = structlog.get_logger()


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts."""

    def __init__(self) -> None:
        # All connected clients
        self._connections: list[WebSocket] = []
        # User-specific connections: email -> list[WebSocket]
        self._user_connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, user_email: str = "") -> None:
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
            if user_email:
                self._user_connections.setdefault(user_email, []).append(ws)
        logger.info("ws_connected", user=user_email, total=len(self._connections))

    async def disconnect(self, ws: WebSocket, user_email: str = "") -> None:
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)
            if user_email and user_email in self._user_connections:
                conns = self._user_connections[user_email]
                if ws in conns:
                    conns.remove(ws)
                if not conns:
                    del self._user_connections[user_email]
        logger.info("ws_disconnected", user=user_email, total=len(self._connections))

    async def broadcast(self, event: dict[str, Any]) -> None:
        """Send event to ALL connected clients."""
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        data = json.dumps(event, default=str)
        async with self._lock:
            dead: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                if ws in self._connections:
                    self._connections.remove(ws)

    async def send_to_user(self, user_email: str, event: dict[str, Any]) -> None:
        """Send event to a specific user's connections."""
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        data = json.dumps(event, default=str)
        async with self._lock:
            conns = self._user_connections.get(user_email, [])
            dead: list[WebSocket] = []
            for ws in conns:
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                if ws in conns:
                    conns.remove(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Singleton
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """
    Client connects with: ws://host/ws?email=user@example.com
    Server pushes events. Client just listens (no messages expected).
    """
    user_email = ws.query_params.get("email", "")
    await manager.connect(ws, user_email)
    try:
        while True:
            # Keep connection alive; we don't expect client messages
            # but we read to detect disconnects
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws, user_email)
    except Exception:
        await manager.disconnect(ws, user_email)


# ─── Helper functions called from other parts of the app ──────────────────

async def broadcast_request_created(
    ticket_key: str,
    request_type: str,
    resource_name: str,
    team_name: str,
    environment: str,
    requester_email: str,
) -> None:
    """Broadcast when a new request is submitted."""
    await manager.broadcast({
        "type": "request_created",
        "ticket_key": ticket_key,
        "request_type": request_type,
        "resource_name": resource_name,
        "team_name": team_name,
        "environment": environment,
        "requester_email": requester_email,
        "message": f"New {request_type} request: {resource_name} ({ticket_key})",
    })


async def broadcast_status_changed(
    ticket_key: str,
    request_type: str,
    resource_name: str,
    old_status: str,
    new_status: str,
    requester_email: str,
) -> None:
    """Broadcast when a request status changes (pipeline progress)."""
    await manager.broadcast({
        "type": "status_changed",
        "ticket_key": ticket_key,
        "request_type": request_type,
        "resource_name": resource_name,
        "old_status": old_status,
        "new_status": new_status,
        "message": f"{ticket_key} ({resource_name}): {old_status} → {new_status}",
    })
    # Also send a targeted notification to the requester
    await notify_user(
        requester_email,
        title=f"{ticket_key} status updated",
        message=f"Your {request_type} request moved to {new_status}",
        ticket_key=ticket_key,
        severity="info" if new_status != "failed" else "error",
    )


async def notify_user(
    user_email: str,
    title: str,
    message: str,
    ticket_key: str = "",
    severity: str = "info",
) -> None:
    """Send a notification to a specific user."""
    await manager.send_to_user(user_email, {
        "type": "notification",
        "title": title,
        "message": message,
        "ticket_key": ticket_key,
        "severity": severity,
    })
