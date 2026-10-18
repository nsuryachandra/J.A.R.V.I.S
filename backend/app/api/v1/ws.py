"""Real-time WebSocket endpoint for JARVIS holographic core communication, telemetry, and live alerts."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["Real-Time WebSockets"])


class ConnectionManager:
    """Manages active holographic WebSocket connections and message broadcasting."""

    def __init__(self):
        self._active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register client WebSocket."""
        await websocket.accept()
        async with self._lock:
            self._active_connections.add(websocket)
        logger.info("Holographic UI WebSocket client connected (%d active)", len(self._active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister client WebSocket on disconnect."""
        async with self._lock:
            self._active_connections.discard(websocket)
        logger.info("Holographic UI WebSocket client disconnected (%d active)", len(self._active_connections))

    async def broadcast(self, message: Dict) -> None:
        """Send JSON message to all connected clients."""
        payload = json.dumps(message)
        async with self._lock:
            stale = []
            for ws in self._active_connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    stale.append(ws)
            for s in stale:
                self._active_connections.discard(s)

    @property
    def active_count(self) -> int:
        return len(self._active_connections)


ws_manager = ConnectionManager()


@router.websocket("/core")
@router.websocket("/live")
async def websocket_core_endpoint(websocket: WebSocket) -> None:
    """Bidirectional WebSocket connection for live telemetry, audio waveforms, and state synchronization."""
    await ws_manager.connect(websocket)

    # Send initial welcome state
    init_event = {
        "type": "CORE_CONNECTED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "ONLINE",
        "system_name": "J.A.R.V.I.S.",
        "version": "1.0.0",
        "orbital_frequency_hz": 60,
    }
    await websocket.send_text(json.dumps(init_event))

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "ERROR", "message": "Invalid JSON format"}))
                continue

            msg_type = data.get("type", "UNKNOWN")

            if msg_type == "PING":
                await websocket.send_text(json.dumps({
                    "type": "PONG",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
            elif msg_type == "QUERY_CORE_STATE":
                await websocket.send_text(json.dumps({
                    "type": "CORE_STATE",
                    "status": "NOMINAL",
                    "arc_reactor_pulse": "STEADY",
                    "active_connections": ws_manager.active_count,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
            elif msg_type == "AUDIO_WAVEFORM_SAMPLE":
                # Echo back normalized amplitude for audio visualizer sync
                await websocket.send_text(json.dumps({
                    "type": "WAVEFORM_ACK",
                    "level": data.get("level", 0.5),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
            else:
                await websocket.send_text(json.dumps({
                    "type": "ECHO",
                    "received": data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning("WebSocket exception: %s", str(exc))
        await ws_manager.disconnect(websocket)
