"""
Real-Time Delta Engine for F1 Telemetry Analyzer
Computes continuous gap (time delta) against a reference lap.
"""
import numpy as np
from typing import Dict, Any, Optional
from scipy.interpolate import interp1d

class RealTimeDelta:
    """
    Computes live delta time against a reference resampled lap.
    Uses the canonical 2048-point s-grid for alignment.
    """
    def __init__(self, reference_resampled: Optional[Dict[str, np.ndarray]] = None):
        self.ref = reference_resampled
        self.ref_v = None
        self.ref_s = None
        self.ref_time_integral = None
        
        if reference_resampled is not None:
            self.update_reference(reference_resampled)

    def update_reference(self, reference_resampled: Dict[str, np.ndarray]):
        """Sets a new reference lap for delta calculation."""
        self.ref = reference_resampled
        self.ref_s = reference_resampled["s"]
        # v in m/s
        self.ref_v = np.clip(reference_resampled["speed"], 0.5, None)
        
        # Pre-calculate time integral (cumulative time along s-grid)
        # dt = ds / v
        ds = np.diff(self.ref_s, append=self.ref_s[-1] + (self.ref_s[1] - self.ref_s[0]))
        dt = ds / self.ref_v
        self.ref_time_integral = np.cumsum(dt)

    def calculate_delta(self, current_s: float, current_v: float, elapsed_lap_time: float) -> float:
        """
        Calculates the live delta at a specific point s.
        delta = current_elapsed_time - reference_elapsed_time_at_s
        """
        if self.ref_time_integral is None:
            return 0.0
            
        # 1. Find reference time at this s
        # Interpolate the pre-calculated time integral
        ref_time_at_s = np.interp(current_s, self.ref_s, self.ref_time_integral)
        
        # 2. Delta is the difference
        delta = elapsed_lap_time - ref_time_at_s
        return float(delta)

    def predict_gain_loss(self, current_s: float, current_v: float) -> float:
        """
        Predicts gain/loss in the next 100m if current speed is maintained.
        """
        if self.ref_v is None: return 0.0
        
        ref_v_at_s = np.interp(current_s, self.ref_s, self.ref_v)
        # Positive = slower than reference
        # (1/v_curr - 1/v_ref) * distance
        prediction = (1.0/max(current_v, 0.1) - 1.0/ref_v_at_s) * 100.0
        return float(prediction)
