"""
ML Feature Engineering for F1 Telemetry Analyzer
Standardizes telemetry into tensors for PyTorch/TensorFlow.
"""
import numpy as np
from typing import Dict, List, Any

class FeatureVectorBuilder:
    """
    Constructs normalized feature vectors and tensors from telemetry.
    Supports fixed-size lap embeddings and corner-level window extraction.
    """
    
    def __init__(self, n_points: int = 2048):
        self.n_points = n_points
        # Canonical channel order for ML
        self.channels = [
            "s_norm", "L_norm", "speed_norm", "throttle", "brake", 
            "kappa_norm", "lat_g_norm", "long_g_norm", "yaw_rate_norm"
        ]

    def build_lap_tensor(self, telemetry: Dict[str, np.ndarray], track_length: float) -> np.ndarray:
        """
        Generates a (N, C) tensor where N is n_points and C is number of channels.
        All values are normalized to roughly [0, 1] or [-1, 1].
        """
        n = self.n_points
        tensor = np.zeros((n, len(self.channels)))
        
        # 1. Normalize spatial channels
        tensor[:, 0] = telemetry["s"] / track_length
        tensor[:, 1] = np.clip(telemetry["L"] / 10.0, -1.5, 1.5) # Normalized by 10m track width
        
        # 2. Normalize physics channels
        tensor[:, 2] = np.clip(telemetry["speed"] / 100.0, 0, 1) # Normalizado por 100 m/s
        tensor[:, 3] = telemetry["throttle"]
        tensor[:, 4] = telemetry["brake"]
        
        # 3. Dynamic channels (from dynamics engine)
        if "curvature" in telemetry:
            tensor[:, 5] = np.clip(telemetry["curvature"] * 100.0, 0, 1)
        if "accel_lat_g" in telemetry:
            tensor[:, 6] = np.clip(telemetry["accel_lat_g"] / 6.0, -1.2, 1.2) # Max 6G
        if "accel_long_g" in telemetry:
            tensor[:, 7] = np.clip(telemetry["accel_long_g"] / 6.0, -1.2, 1.2)
        if "yaw_rate_degs" in telemetry:
            tensor[:, 8] = np.clip(telemetry["yaw_rate_degs"] / 180.0, -1, 1) # Deg/s
            
        return tensor

    def extract_corner_windows(self, lap_tensor: np.ndarray, corners: List[Dict], window_size: int = 256) -> List[np.ndarray]:
        """
        Extracts fixed-size windows centered around apexes for corner classification.
        """
        windows = []
        for corner in corners:
            apex_s_norm = corner["apex_s"] / (corner["end_s"] if corner["end_s"] > 0 else 1.0)
            # Find nearest index in resampled grid
            apex_idx = int(apex_s_norm * self.n_points)
            
            start = apex_idx - window_size // 2
            end = apex_idx + window_size // 2
            
            # Handle boundary conditions with padding or wrapping
            if start >= 0 and end < self.n_points:
                windows.append(lap_tensor[start:end, :])
            else:
                # Simple zero-padding for now
                window = np.zeros((window_size, lap_tensor.shape[1]))
                valid_start = max(0, start)
                valid_end = min(self.n_points, end)
                offset = valid_start - start
                window[offset:offset+(valid_end-valid_start), :] = lap_tensor[valid_start:valid_end, :]
                windows.append(window)
                
        return windows
