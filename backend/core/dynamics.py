"""
Telemetry Dynamics Engine for F1 Telemetry Analyzer
Computes physically-aware signals: G-forces, Yaw Rate, Jerk, 
and input gradients.
"""
import numpy as np
from scipy.signal import savgol_filter
from typing import Dict, Any, Optional

class TelemetryDynamics:
    """
    Computes numerically stable physical signals from telemetry.
    Supports Savitzky-Golay filtering for noise reduction.
    """
    
    def __init__(self, sample_rate: float = 60.0):
        self.dt = 1.0 / sample_rate

    def compute_dynamics(self, resampled_lap: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """
        Computes all physics-derived channels for a resampled lap.
        All inputs expected in SI units (m/s, meters).
        """
        # 1. Basic channels
        v = np.asarray(resampled_lap["speed"], dtype=float)
        s = np.asarray(resampled_lap["s"], dtype=float)
        
        # Approximate time delta between resampled points
        # s = v * t -> dt = ds / v
        ds = np.diff(s, append=s[-1] + (s[1] - s[0]))
        v_clamped = np.clip(v, 0.5, None)
        dt_seq = ds / v_clamped
        
        # 2. Longitudinal Acceleration (G-force)
        # dv/dt
        dv = np.diff(v, append=v[-1])
        accel_long_ms2 = dv / dt_seq
        # Apply light smoothing to reduce noise spikes
        accel_long_ms2 = savgol_filter(accel_long_ms2, window_length=11, polyorder=2)
        
        # 3. Lateral Acceleration (v^2 / R or v * yaw_rate)
        # We need curvature κ to get R = 1/κ
        if "curvature" in resampled_lap:
            kappa = resampled_lap["curvature"]
        else:
            # Fallback to coordinate-derived curvature
            kappa = self._compute_curvature(resampled_lap["x"], resampled_lap["z"])
            
        accel_lat_ms2 = (v**2) * kappa
        accel_lat_ms2 = savgol_filter(accel_lat_ms2, window_length=11, polyorder=2)

        # 4. Yaw Rate (rad/s)
        # omega = v * kappa
        yaw_rate = v * kappa
        
        # 5. Jerk (d_accel/dt)
        da = np.diff(accel_long_ms2, append=accel_long_ms2[-1])
        jerk = da / dt_seq
        
        # 6. Input Gradients (Smoothness)
        throttle = resampled_lap["throttle"]
        brake = resampled_lap["brake"]
        
        d_throttle = np.diff(throttle, append=throttle[-1]) / dt_seq
        d_brake = np.diff(brake, append=brake[-1]) / dt_seq

        return {
            "accel_long_g": accel_long_ms2 / 9.81,
            "accel_lat_g": accel_lat_ms2 / 9.81,
            "yaw_rate_degs": np.degrees(yaw_rate),
            "jerk_ms3": jerk,
            "throttle_gradient": d_throttle,
            "brake_gradient": d_brake,
            "curvature": kappa
        }

    def _compute_curvature(self, x: np.ndarray, z: np.ndarray) -> np.ndarray:
        """Computes curvature from coordinates using discrete derivatives."""
        dx = np.gradient(x)
        dz = np.gradient(z)
        ddx = np.gradient(dx)
        ddz = np.gradient(dz)
        
        num = np.abs(dx * ddz - dz * ddx)
        den = (dx**2 + dz**2)**1.5
        den[den == 0] = 1e-10
        
        return num / den
