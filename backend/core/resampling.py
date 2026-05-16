"""
Telemetry Resampling Engine
Standardizes telemetry samples onto a canonical s-grid for comparative 
analysis and ML training.
"""
import numpy as np
from scipy.interpolate import interp1d
from typing import Dict, List, Any, Optional

class TelemetryResampler:
    """
    Standardizes telemetry onto a fixed s-grid.
    Default resolution: 2048 points.
    """
    
    def __init__(self, n_points: int = 2048):
        self.n_points = n_points

    def resample_lap(self, lap_data: Dict[str, np.ndarray], total_length: float) -> Dict[str, np.ndarray]:
        """
        Resamples all channels in a lap onto a fixed s-grid.
        
        Args:
            lap_data: Dict containing 's', 'L', 'speed', 'throttle', 'brake', etc.
            total_length: Total track length (meters)
            
        Returns:
            Dict with resampled channels, all of length n_points.
        """
        s_src = lap_data["s"]
        
        # 1. Create canonical s-grid
        s_target = np.linspace(0, total_length, self.n_points)
        
        # 2. Sort and remove duplicates in source s (required for interpolation)
        # Lap wrap-around might create s values near 0 at the end if not handled.
        # We assume s_src is mostly monotonic.
        s_src = np.asarray(s_src)
        
        # Handle wrap around if any
        # (This should be handled by project_sequence, but we ensure it here)
        unique_mask = np.concatenate([[True], np.diff(s_src) != 0])
        s_u = s_src[unique_mask]
        
        # If s_u is not monotonic, we sort it. 
        # For a full lap, we expect it to be mostly monotonic from 0 to total_length.
        sort_idx = np.argsort(s_u)
        s_u = s_u[sort_idx]
        
        resampled = {"s": s_target}
        
        channels = [k for k in lap_data.keys() if k != "s"]
        
        for channel in channels:
            data = np.asarray(lap_data[channel])[unique_mask][sort_idx]
            
            # Linear interpolation for speed and inputs
            # Cubic might create overshoot for throttle/brake
            kind = 'linear' if channel in ('throttle', 'brake') else 'cubic'
            
            f = interp1d(s_u, data, kind=kind, bounds_error=False, fill_value="extrapolate")
            resampled[channel] = f(s_target)
            
            # Post-processing: ensure inputs are clipped
            if channel in ('throttle', 'brake'):
                resampled[channel] = np.clip(resampled[channel], 0, 1)
            elif channel == 'speed':
                resampled[channel] = np.clip(resampled[channel], 0, None)
                
        return resampled

    def calculate_delta_time(self, player_resampled: Dict, ref_resampled: Dict) -> np.ndarray:
        """
        Calculates delta time between two resampled laps.
        dt = ds / v
        Delta(s) = sum( (ds/v_player) - (ds/v_ref) )
        """
        s = player_resampled["s"]
        v_p = np.clip(player_resampled["speed"], 0.1, None)
        v_r = np.clip(ref_resampled["speed"], 0.1, None)
        
        ds = np.diff(s, append=s[-1] + (s[1] - s[0]))
        
        dt_p = ds / v_p
        dt_r = ds / v_r
        
        delta = np.cumsum(dt_p - dt_r)
        return delta
