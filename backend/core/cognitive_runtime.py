"""
Lightweight runtime for streaming driver cognitive state to the UI.

This intentionally uses only the cheap cognitive/state estimators. The heavier
RaceEngineerAgent also runs foundation/trajectory models and is not suitable
for per-frame UI status without a separate throttle/feature flag.
"""
import logging
import time
from typing import Any, Dict

from core.driver_cognitive_model import DriverCognitiveModel
from core.driver_state_estimator import DriverStateEstimator
from core.telemetry_events import DRIVER_COG_STATE, PROCESSED_FRAME, event_bus

logger = logging.getLogger(__name__)


class CognitiveRuntime:
    """Consumes processed telemetry frames and emits a throttled cognitive state."""

    def __init__(self, min_interval_seconds: float = 0.5):
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self.cognitive_model = DriverCognitiveModel()
        self.state_estimator = DriverStateEstimator()
        self._running = False
        self._last_emit_at = 0.0

    def start(self):
        if self._running:
            return
        event_bus.subscribe(PROCESSED_FRAME, self.on_frame)
        self._running = True
        logger.info("Cognitive runtime started")

    def stop(self):
        if not self._running:
            return
        event_bus.unsubscribe(PROCESSED_FRAME, self.on_frame)
        self._running = False
        logger.info("Cognitive runtime stopped")

    async def on_frame(self, frame: Dict[str, Any]):
        normalized = self._normalize_frame(frame)
        metrics = self.cognitive_model.update(normalized)
        now = time.perf_counter()

        if now - self._last_emit_at < self.min_interval_seconds:
            return

        state = self.state_estimator.estimate_state(metrics, physics_anomalies=0)
        self._last_emit_at = now
        await event_bus.emit(
            DRIVER_COG_STATE,
            {
                "type": DRIVER_COG_STATE,
                "metrics": metrics,
                "state": state,
                "timestamp": normalized.get("timestamp") or time.time(),
            },
        )

    @staticmethod
    def _normalize_frame(frame: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(frame)
        if "steer" not in normalized and "steering" in normalized:
            normalized["steer"] = normalized.get("steering")
        return normalized
