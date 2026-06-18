"""
Websocket Server for F1 Telemetry Analyzer
Broadcasts real-time telemetry frames and events to connected clients.
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional
import json
import logging
import asyncio
import os
import time

from core.performance_metrics import performance_metrics
from core.telemetry_events import OPPONENTS_FRAME, event_bus

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages active websocket connections."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._broadcast_lock = asyncio.Lock()
        self.send_timeout_seconds = max(float(os.getenv("TELEMETRY_WS_SEND_TIMEOUT", "0.25")), 0.05)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return

        started = time.perf_counter()
        msg_str = json.dumps(message, separators=(",", ":"), default=str)
        async with self._broadcast_lock:
            performance_metrics.mark_websocket_message(message_type=message.get("type"))
            connections = list(self.active_connections)
            tasks = [
                asyncio.wait_for(conn.send_text(msg_str), timeout=self.send_timeout_seconds)
                for conn in connections
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for conn, result in zip(connections, results):
                if isinstance(result, Exception):
                    logger.debug("Dropping stale websocket connection: %s", result)
                    self.disconnect(conn)
            performance_metrics.record_websocket_send(time.perf_counter() - started)

class TelemetryBroadcaster:
    """
    Subscribes to the internal event bus and forwards 
    relevant events to the websocket manager.
    """
    def __init__(
        self,
        manager: ConnectionManager,
        *,
        subscribe: bool = True,
        frame_hz: Optional[float] = None,
    ):
        self.manager = manager
        configured_hz = frame_hz if frame_hz is not None else float(os.getenv("TELEMETRY_WS_HZ", "90"))
        self.frame_interval = 1.0 / max(configured_hz, 1.0)
        opponents_hz = float(os.getenv("OPPONENTS_WS_HZ", "10"))
        self.opponents_interval = 1.0 / max(opponents_hz, 1.0)
        self._latest_frame: Optional[Dict[str, Any]] = None
        self._frame_sender_task: Optional[asyncio.Task] = None
        self._last_frame_sent_at = 0.0
        self._latest_opponents: Optional[Dict[str, Any]] = None
        self._opponents_sender_task: Optional[asyncio.Task] = None
        self._last_opponents_sent_at = 0.0

        if subscribe:
            event_bus.subscribe("processed_frame", self.on_frame)
            event_bus.subscribe(OPPONENTS_FRAME, self.on_opponents)
            event_bus.subscribe("sector_split", self.on_event)
            event_bus.subscribe("lap_finalized", self.on_event)
            event_bus.subscribe("coaching_event", self.on_event)
            event_bus.subscribe("physics_anomaly", self.on_event)

    async def on_frame(self, frame: Dict[str, Any]):
        if self._latest_frame is not None:
            performance_metrics.mark_websocket_frame_coalesced()
        self._latest_frame = frame
        if self._frame_sender_task is None or self._frame_sender_task.done():
            self._frame_sender_task = asyncio.create_task(self._drain_frames())

    async def _drain_frames(self):
        try:
            while self._latest_frame is not None:
                delay = self.frame_interval - (time.monotonic() - self._last_frame_sent_at)
                if delay > 0:
                    await asyncio.sleep(delay)
                frame = self._latest_frame
                self._latest_frame = None
                self._last_frame_sent_at = time.monotonic()
                await self.manager.broadcast({"type": "telemetry", "data": frame})
                await self._broadcast_pending_opponents()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telemetry websocket sender failed")

    async def on_opponents(self, data: Dict[str, Any]):
        self._latest_opponents = data
        if self._frame_sender_task is not None and not self._frame_sender_task.done():
            return
        if self._opponents_sender_task is None or self._opponents_sender_task.done():
            self._opponents_sender_task = asyncio.create_task(self._drain_opponents())

    async def _broadcast_pending_opponents(self):
        if self._latest_opponents is None:
            return
        if time.monotonic() - self._last_opponents_sent_at < self.opponents_interval:
            return
        opponents = self._latest_opponents
        self._latest_opponents = None
        self._last_opponents_sent_at = time.monotonic()
        await self.manager.broadcast({"type": "opponents", "data": opponents})

    async def _drain_opponents(self):
        try:
            while self._latest_opponents is not None:
                delay = self.opponents_interval - (time.monotonic() - self._last_opponents_sent_at)
                if delay > 0:
                    await asyncio.sleep(delay)
                if self._frame_sender_task is not None and not self._frame_sender_task.done():
                    return
                await self._broadcast_pending_opponents()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Opponents websocket sender failed")

    def pending_depth(self) -> int:
        return int(self._latest_frame is not None) + int(self._latest_opponents is not None)

    async def on_event(self, data: Dict[str, Any]):
        await self.manager.broadcast({
            "type": "event",
            "data": data
        })

# Global manager instance
manager = ConnectionManager()
broadcaster = TelemetryBroadcaster(manager)
