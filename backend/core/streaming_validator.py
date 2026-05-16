"""
Streaming Physics Validator
Monitors real-time telemetry for physical consistency and integrity.
"""
import logging
from typing import Dict, Any
from core.telemetry_events import event_bus
from core.config import MAX_ACCEL_G, MAX_BRAKE_G, MAX_SPEED_KMH

logger = logging.getLogger(__name__)

class StreamingValidator:
    """
    Performs live integrity checks on processed telemetry frames.
    Flags anomalies like teleportation, impossible acceleration, or speed violations.
    """
    def __init__(self):
        # Subscribe to processed frames
        event_bus.subscribe("processed_frame", self.validate_frame)
        self.anomalies_count = 0

    async def validate_frame(self, frame: Dict[str, Any]):
        """Checks a single frame for physical validity."""
        speed_kmh = frame["speed"] * 3.6
        accel_g = frame.get("accel_g", 0.0)
        
        reasons = []
        
        # 1. Speed Check
        if speed_kmh > MAX_SPEED_KMH * 1.1:
            reasons.append(f"Excessive speed: {speed_kmh:.1f} km/h")
            
        # 2. Acceleration Checks
        if accel_g > MAX_ACCEL_G * 1.5:
            reasons.append(f"Impossible longitudinal accel: {accel_g:.2f} G")
        elif accel_g < -MAX_BRAKE_G * 1.5:
            reasons.append(f"Impossible braking force: {accel_g:.2f} G")
            
        # 3. Spatial Checks (Track Limits can be integrated here)
        L = frame.get("L", 0.0)
        if abs(L) > 20.0: # 20m off centerline is usually a massive excursion
            reasons.append(f"Extreme spatial deviation: L={L:.1f}m")
            
        if reasons:
            self.anomalies_count += 1
            await event_bus.emit("physics_anomaly", {
                "timestamp": frame["timestamp"],
                "driver_id": frame.get("driver_id", "player_1"),
                "reasons": reasons,
                "frame": frame
            })
            if self.anomalies_count % 10 == 0:
                logger.warning(f"Physics Anomaly Detected: {', '.join(reasons)}")
