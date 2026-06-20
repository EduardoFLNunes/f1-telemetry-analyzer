"""
Internal Event Bus for F1 Telemetry Analyzer
Decouples telemetry ingestion from processing and storage.
"""
import asyncio
import threading
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
        self._scheduled_pending = 0
        self._scheduled_by_topic: Dict[str, int] = {}
        self._scheduled_total = 0
        self._scheduled_failed = 0
        self._schedule_lock = threading.Lock()

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

    def schedule(self, event_type: str, data: Any, loop: asyncio.AbstractEventLoop):
        with self._schedule_lock:
            self._scheduled_pending += 1
            self._scheduled_total += 1
            self._scheduled_by_topic[event_type] = self._scheduled_by_topic.get(event_type, 0) + 1
        try:
            future = asyncio.run_coroutine_threadsafe(self.emit(event_type, data), loop)
        except Exception:
            self._finish_scheduled(event_type, failed=True)
            raise

        def done(completed):
            failed = completed.cancelled()
            if not failed:
                try:
                    failed = completed.exception() is not None
                except Exception:
                    failed = True
            self._finish_scheduled(event_type, failed=failed)

        future.add_done_callback(done)
        return future

    def snapshot(self) -> Dict[str, Any]:
        with self._schedule_lock:
            return {
                "pendingTasks": self._scheduled_pending,
                "pendingByTopic": dict(self._scheduled_by_topic),
                "scheduledTotal": self._scheduled_total,
                "failedTasks": self._scheduled_failed,
            }

    def _finish_scheduled(self, event_type: str, failed: bool):
        with self._schedule_lock:
            self._scheduled_pending = max(0, self._scheduled_pending - 1)
            topic_pending = max(0, self._scheduled_by_topic.get(event_type, 0) - 1)
            if topic_pending:
                self._scheduled_by_topic[event_type] = topic_pending
            else:
                self._scheduled_by_topic.pop(event_type, None)
            if failed:
                self._scheduled_failed += 1

# Global event bus instance
event_bus = TelemetryEventBus()
