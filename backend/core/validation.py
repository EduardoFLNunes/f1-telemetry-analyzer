"""
Telemetry Validation Layer
Detects corrupted, non-physical, or unstable telemetry data.
Ensures ML dataset integrity.
"""
import numpy as np
from typing import Dict, List, Tuple, Any

class TelemetryValidator:
    """
    Validates telemetry samples and sequences for physical realism 
    and spatial stability.
    """
    
    def __init__(self):
        # Physical constraints for F1-class vehicles
        self.MAX_ACCEL = 60.0 # m/s^2 (approx 6G)
        self.MAX_BRAKE = 70.0 # m/s^2 (approx 7G)
        self.MAX_SPEED = 100.0 # m/s (~360 km/h)
        self.MAX_S_JUMP = 20.0 # meters between samples (at ~10Hz)

    def validate_lap(self, lap_data: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """
        Performs comprehensive validation of a full lap.
        Returns a report with 'valid' status and identified issues.
        """
        issues = []
        valid = True
        
        # 1. Check for NaNs
        for key, arr in lap_data.items():
            if np.isnan(arr).any():
                issues.append(f"NaN detected in channel: {key}")
                valid = False

        # 2. Spatial Stability (s-continuity)
        s = lap_data["s"]
        ds = np.diff(s)
        # Filter out lap wrap-around jumps
        # A jump from total_length to 0 will have a large negative ds
        # We only care about large POSITIVE jumps that aren't physical
        jumps = ds[ds > self.MAX_S_JUMP]
        if len(jumps) > 0:
            issues.append(f"Spatial instability: {len(jumps)} jumps detected in lap distance")
            valid = False
            
        # 3. Physical Realism (Speed/Acceleration)
        if "speed" in lap_data:
            v = lap_data["speed"]
            if v.max() > self.MAX_SPEED:
                issues.append(f"Speed exceeds physical limit: {v.max():.1f} m/s")
                # Don't necessarily invalidate, but flag
                
            # Acceleration check (requires session_time)
            if "session_time" in lap_data:
                t = lap_data["session_time"]
                dt = np.diff(t)
                dt[dt == 0] = 1e-6
                dv = np.diff(v)
                accel = dv / dt
                
                if accel.max() > self.MAX_ACCEL:
                    issues.append(f"Unphysical acceleration: {accel.max():.1f} m/s^2")
                    valid = False
                if accel.min() < -self.MAX_BRAKE:
                    issues.append(f"Unphysical braking: {accel.min():.1f} m/s^2")
                    valid = False

        return {
            "valid": valid,
            "issues": issues,
            "integrity_score": self._calculate_integrity(lap_data, issues)
        }

    def _calculate_integrity(self, lap_data: Dict, issues: List[str]) -> float:
        """Calculates a score from 0.0 to 1.0 representing data quality."""
        if not issues: return 1.0
        # Simple deduction model
        score = 1.0 - (len(issues) * 0.1)
        return max(0.0, score)
