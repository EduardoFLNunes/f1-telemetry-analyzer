"""
Coaching Intelligence Engine
Generates deterministic driver feedback events by comparing telemetry against a reference.
"""
from typing import Dict, Any, Optional, List
import logging
import numpy as np

logger = logging.getLogger(__name__)

class CoachingEngine:
    """
    Real-time analyzer for driver performance optimization.
    Detects errors in braking, throttle application, and apex positioning.
    """
    def __init__(self, reference_lap: Optional[Dict[str, np.ndarray]] = None):
        self.ref = reference_lap
        self.last_frame: Optional[Dict[str, Any]] = None
        self.active_events: Dict[str, Dict[str, Any]] = {}
        
        # Thresholds
        self.BRAKE_THRESHOLD = 0.1
        self.THROTTLE_THRESHOLD = 0.1
        self.APEX_L_TOLERANCE = 1.5 # meters

    def update_reference(self, reference_lap: Dict[str, np.ndarray]):
        self.ref = reference_lap

    def process_frame(self, current: Dict[str, Any], corner: Optional[Any] = None) -> List[Dict[str, Any]]:
        """
        Analyzes the current frame and returns a list of detected coaching events.
        """
        if self.ref is None or self.last_frame is None:
            self.last_frame = current
            return []

        events = []
        
        # 1. Braking Analysis
        brake_event = self._analyze_braking(current)
        if brake_event: events.append(brake_event)
        
        # 2. Throttle Analysis
        throttle_event = self._analyze_throttle(current)
        if throttle_event: events.append(throttle_event)
        
        # 3. Apex Analysis
        if corner:
            apex_event = self._analyze_apex(current, corner)
            if apex_event: events.append(apex_event)
            
        self.last_frame = current
        return events

    def _analyze_braking(self, current: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detects late/early braking by comparing current s to reference brake s."""
        curr_s = current["s"]
        curr_brake = current["brake"]
        prev_brake = self.last_frame["brake"]
        
        # Detect start of braking
        if curr_brake > self.BRAKE_THRESHOLD and prev_brake <= self.BRAKE_THRESHOLD:
            # Find closest s in reference where brake > threshold
            ref_s = self.ref["s"]
            ref_brake = self.ref["brake"]
            ref_brake_idxs = np.where(ref_brake > self.BRAKE_THRESHOLD)[0]
            
            if len(ref_brake_idxs) > 0:
                # Find the start of the nearest braking zone in reference
                # This is a simplified search; in production we'd use a windowed search
                closest_ref_idx = np.argmin(np.abs(ref_s - curr_s))
                # Search backwards for the start of this zone
                zone_start_idx = ref_brake_idxs[np.argmin(np.abs(ref_s[ref_brake_idxs] - curr_s))]
                ref_start_s = ref_s[zone_start_idx]
                
                delta_s = curr_s - ref_start_s
                
                if abs(delta_s) > 5.0: # 5 meter threshold
                    event_type = "late_brake" if delta_s > 0 else "early_brake"
                    return {
                        "type": "coaching_event",
                        "event": event_type,
                        "severity": min(abs(delta_s) / 20.0, 1.0),
                        "evidence": {
                            "delta_m": float(delta_s),
                            "ref_s": float(ref_start_s),
                            "curr_s": float(curr_s)
                        }
                    }
        return None

    def _analyze_throttle(self, current: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detects throttle hesitation or early application."""
        curr_throttle = current["throttle"]
        prev_throttle = self.last_frame["throttle"]
        
        # Detect throttle oscillation (hesitation)
        # If throttle was increasing but now decreasing before reaching 90%
        if 0.2 < prev_throttle < 0.9 and curr_throttle < prev_throttle - 0.05:
            return {
                "type": "coaching_event",
                "event": "throttle_hesitation",
                "severity": 0.5,
                "evidence": {
                    "prev_throttle": float(prev_throttle),
                    "curr_throttle": float(curr_throttle)
                }
            }
        return None

    def _analyze_apex(self, current: Dict[str, Any], corner: Any) -> Optional[Dict[str, Any]]:
        """Detects poor apex positioning."""
        curr_s = current["s"]
        curr_L = current["L"]
        
        # If we are near the apex
        if abs(curr_s - corner.apex_s) < 2.0:
            # Check if L is significantly different from 0 (or reference L)
            # Assuming reference L at apex is 0 for simplicity
            if abs(curr_L) > self.APEX_L_TOLERANCE:
                return {
                    "type": "coaching_event",
                    "event": "poor_apex",
                    "severity": min(abs(curr_L) / 5.0, 1.0),
                    "evidence": {
                        "corner_id": corner.corner_id,
                        "l_offset": float(curr_L),
                        "apex_s": float(corner.apex_s)
                    }
                }
        return None
