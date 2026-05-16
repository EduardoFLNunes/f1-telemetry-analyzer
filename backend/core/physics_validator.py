"""
Telemetry Physics Validator
Ensures telemetry signals obey laws of physics and numerical stability.
"""
import numpy as np
from typing import Dict, List, Any

class TelemetryPhysicsValidator:
    """
    Identifies non-physical telemetry or numerical artifacts.
    """
    
    def __init__(self):
        # Physics boundaries for modern F1 cars
        self.MAX_LAT_G = 7.5
        self.MAX_LONG_G_ACCEL = 4.5
        self.MAX_LONG_G_BRAKE = 7.0
        self.MAX_YAW_RATE = 250.0 # deg/s
        self.MAX_JERK = 200.0 # m/s^3

    def validate_dynamics(self, dynamics: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """
        Checks computed dynamics for physical plausibility.
        """
        issues = []
        valid = True
        
        # 1. Lateral G check
        lat_g = dynamics["accel_lat_g"]
        if np.abs(lat_g).max() > self.MAX_LAT_G:
            issues.append(f"Excessive Lateral G: {np.abs(lat_g).max():.1f}G")
            valid = False
            
        # 2. Longitudinal G check
        long_g = dynamics["accel_long_g"]
        if long_g.max() > self.MAX_LONG_G_ACCEL:
            issues.append(f"Excessive Accel G: {long_g.max():.1f}G")
        if long_g.min() < -self.MAX_LONG_G_BRAKE:
            issues.append(f"Excessive Braking G: {long_g.min():.1f}G")
            valid = False
            
        # 3. Yaw Rate check
        yaw = dynamics["yaw_rate_degs"]
        if np.abs(yaw).max() > self.MAX_YAW_RATE:
            issues.append(f"Unrealistic Yaw Rate: {np.abs(yaw).max():.1f} deg/s")
            valid = False
            
        # 4. Numerical Stability (Jerk)
        jerk = dynamics["jerk_ms3"]
        if np.abs(jerk).max() > self.MAX_JERK:
            issues.append(f"Numerical instability or crash detected (Jerk): {np.abs(jerk).max():.1f} m/s^3")
            
        return {
            "valid": valid,
            "issues": issues,
            "phys_integrity": 1.0 - (len(issues) * 0.15)
        }
