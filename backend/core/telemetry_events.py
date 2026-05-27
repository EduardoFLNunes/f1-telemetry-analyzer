"""
Internal Event Bus for F1 Telemetry Analyzer
Decouples telemetry ingestion from processing and storage.
"""
import asyncio
from typing import Dict, Any, Callable, List
import logging

logger = logging.getLogger(__name__)

# Phase 2 Core Events
RAW_PACKET = "raw_packet"
NORMALIZED_FRAME = "normalized_frame"
PROCESSED_FRAME = "processed_frame"
OPPONENTS_FRAME = "opponents_frame"
SECTOR_SPLIT = "sector_split"
LAP_FINALIZED = "lap_finalized"

# Phase 3 Intelligence Events
COACHING_EVENT = "coaching_event"
PHYSICS_ANOMALY = "physics_anomaly"
CORNER_EVENT = "corner_event"
EMBEDDING_EVENT = "embedding_event"
SESSION_INSIGHT = "session_insight_event"
PREDICTION_EVENT = "prediction_event"
DRIVER_COG_STATE = "driver_cognitive_state"
ENGINEER_SPEECH = "engineer_speech"

class TelemetryEventBus:
    """
    Simple async event bus for real-time telemetry distribution.
    """
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        if callback not in self.subscribers[event_type]:
            self.subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)
            logger.debug(f"Unsubscribed from {event_type}")

    async def emit(self, event_type: str, data: Any):
        if event_type in self.subscribers:
            tasks = [cb(data) for cb in self.subscribers[event_type]]
            await asyncio.gather(*tasks)

# Global event bus instance
event_bus = TelemetryEventBus()
