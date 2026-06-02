"""
Websocket Server for F1 Telemetry Analyzer
Broadcasts real-time telemetry frames and events to connected clients.
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
import logging
import asyncio

from core.performance_metrics import performance_metrics
from core.telemetry_events import DRIVER_COG_STATE, ENGINEER_SPEECH, OPPONENTS_FRAME, event_bus

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages active websocket connections."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

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
            
        # Serialize to JSON
        msg_str = json.dumps(message)
        performance_metrics.mark_websocket_message()
        
        # Broadcast to all connected clients
        # In production, we'd use a per-driver subscription model
        connections = list(self.active_connections)
        tasks = [conn.send_text(msg_str) for conn in connections]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for conn, result in zip(connections, results):
            if isinstance(result, Exception):
                logger.debug("Dropping stale websocket connection: %s", result)
                self.disconnect(conn)

class TelemetryBroadcaster:
    """
    Subscribes to the internal event bus and forwards 
    relevant events to the websocket manager.
    """
    def __init__(self, manager: ConnectionManager):
        self.manager = manager
        
        # Subscribe to events we want to stream to the UI
        event_bus.subscribe("processed_frame", self.on_frame)
        event_bus.subscribe(OPPONENTS_FRAME, self.on_opponents)
        event_bus.subscribe("sector_split", self.on_event)
        event_bus.subscribe("lap_finalized", self.on_event)
        
        # Phase 3 Events
        event_bus.subscribe("coaching_event", self.on_event)
        event_bus.subscribe("physics_anomaly", self.on_event)
        event_bus.subscribe(DRIVER_COG_STATE, self.on_event)
        event_bus.subscribe(ENGINEER_SPEECH, self.on_event)

    async def on_frame(self, frame: Dict[str, Any]):
        await self.manager.broadcast({
            "type": "telemetry",
            "data": frame
        })

    async def on_opponents(self, data: Dict[str, Any]):
        await self.manager.broadcast({
            "type": "opponents",
            "data": data
        })

    async def on_event(self, data: Dict[str, Any]):
        await self.manager.broadcast({
            "type": "event",
            "data": data
        })

# Global manager instance
manager = ConnectionManager()
broadcaster = TelemetryBroadcaster(manager)
