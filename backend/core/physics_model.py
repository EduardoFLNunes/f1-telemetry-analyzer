"""
Track Physics Model for F1 Telemetry Analyzer
Provides curvature profiling, apex detection, and phase segmentation.
"""
import numpy as np
from typing import Dict, List, Any, Tuple
from scipy.signal import find_peaks

class TrackPhysicsModel:
    """
    Analyzes track geometry from a physical perspective.
    Identifies apexes and segments corners into approach, braking, and exit phases.
    """
    
    def __init__(self, track_data: Dict[str, Any]):
        self.track_data = track_data
        self.spatial_index = track_data.get("_spatial_index")
        
        # Curvature profile (kappa vs s)
        self.s_grid = self.spatial_index.s_samples if self.spatial_index else np.array([])
        # Compute curvature at sample points
        if self.spatial_index:
            self.kappa = self._compute_kappa(self.s_grid)
        else:
            self.kappa = np.array([])

    def segment_corners(self) -> List[Dict[str, Any]]:
        """
        Identifies and segments corners using the curvature profile.
        """
        if len(self.kappa) == 0: return []
        
        # 1. Find local maxima of curvature (apexes)
        # Threshold to ignore minor track kinks
        KAPPA_THRESHOLD = 0.002 
        peaks, _ = find_peaks(self.kappa, height=KAPPA_THRESHOLD, distance=20)
        
        corners = []
        for i, apex_idx in enumerate(peaks):
            apex_s = self.s_grid[apex_idx]
            kappa_max = self.kappa[apex_idx]
            
            # 2. Expand around apex to find corner boundaries
            # A corner ends when curvature drops below a % of peak or a base threshold
            start_idx, end_idx = self._expand_corner(apex_idx, KAPPA_THRESHOLD)
            
            corners.append({
                "corner_id": i + 1,
                "apex_s": float(apex_s),
                "start_s": float(self.s_grid[start_idx]),
                "end_s": float(self.s_grid[end_idx]),
                "max_curvature": float(kappa_max),
                "radius_min": float(1.0 / kappa_max) if kappa_max > 0 else float('inf'),
                "type": "tight" if kappa_max > 0.01 else "medium"
            })
            
        return corners

    def _compute_kappa(self, s: np.ndarray) -> np.ndarray:
        """Computes curvature kappa at given s using spline derivatives."""
        # kappa = |x'z'' - z'x''| / (x'^2 + z'^2)^1.5
        # Since s is arc-length, denominator is 1.0
        dx = self.spatial_index.spline_x(s, 1)
        dz = self.spatial_index.spline_z(s, 1)
        ddx = self.spatial_index.spline_x(s, 2)
        ddz = self.spatial_index.spline_z(s, 2)
        
        return np.abs(dx * ddz - dz * ddx)

    def _expand_corner(self, apex_idx: int, threshold: float) -> Tuple[int, int]:
        """Expands around apex until curvature drops below threshold."""
        n = len(self.kappa)
        start = apex_idx
        end = apex_idx
        
        # Expand backwards
        while start > 0 and self.kappa[start] > threshold:
            start -= 1
            
        # Expand forwards
        while end < n - 1 and self.kappa[end] > threshold:
            end += 1
            
        return start, end
