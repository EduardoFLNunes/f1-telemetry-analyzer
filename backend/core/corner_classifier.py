"""
Corner Archetype Classifier
Analyzes track geometry to identify and classify corners.
"""
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from core.spatial import TrackSpline

@dataclass
class CornerArchetype:
    corner_id: int
    s_start: float
    s_end: float
    apex_s: float
    direction: str  # "left" or "right"
    archetype: str  # "hairpin", "chicane", "sweeper", "kink", "normal"
    max_curvature: float
    length: float

class CornerClassifier:
    """
    Analyzes curvature profile to segment and classify corners.
    """
    def __init__(self, spline: TrackSpline, threshold_kappa: float = 0.01):
        self.spline = spline
        self.threshold_kappa = threshold_kappa
        self.corners: List[CornerArchetype] = []

    def classify_track(self) -> List[CornerArchetype]:
        """
        Main entry point for track analysis.
        """
        # 1. Sample curvature along the entire track
        s_grid = np.linspace(0, self.spline.total_length, 2048)
        kappa = self._calculate_curvature(s_grid)
        
        # 2. Identify candidate segments where kappa > threshold
        is_corner = np.abs(kappa) > self.threshold_kappa
        
        # 3. Group contiguous corner segments
        segments = self._find_segments(is_corner, s_grid)
        
        # 4. Refine and classify each segment
        self.corners = []
        for i, (s_start, s_end) in enumerate(segments):
            # Sample refined grid for this segment
            s_seg = np.linspace(s_start, s_end, 100)
            kappa_seg = self._calculate_curvature(s_seg)
            
            # Find apex (max absolute curvature)
            abs_kappa = np.abs(kappa_seg)
            apex_idx = np.argmax(abs_kappa)
            apex_s = s_seg[apex_idx]
            max_k = kappa_seg[apex_idx]
            
            # Basic classification logic
            length = s_end - s_start
            radius = 1.0 / (abs(max_k) + 1e-6)
            direction = "left" if max_k > 0 else "right"
            
            # Simple archetype heuristics
            if length < 20 and abs(max_k) < 0.03:
                archetype = "kink"
            elif radius < 15:
                archetype = "hairpin"
            elif length > 150:
                archetype = "sweeper"
            else:
                archetype = "normal"
                
            # TODO: Detect chicanes by looking for sign changes in kappa
            
            self.corners.append(CornerArchetype(
                corner_id=i+1,
                s_start=s_start,
                s_end=s_end,
                apex_s=apex_s,
                direction=direction,
                archetype=archetype,
                max_curvature=float(max_k),
                length=length
            ))
            
        return self.corners

    def _calculate_curvature(self, s: np.ndarray) -> np.ndarray:
        """
        Calculates signed curvature kappa(s).
        kappa = (x'z'' - z'x'') / (x'^2 + z'^2)^1.5
        Since s is arc-length, denom is 1.0.
        """
        s_mod = s % self.spline.total_length
        dx = self.spline.spline_x(s_mod, 1)
        dz = self.spline.spline_z(s_mod, 1)
        ddx = self.spline.spline_x(s_mod, 2)
        ddz = self.spline.spline_z(s_mod, 2)
        
        # Signed curvature (assuming z is "forward" and x is "right")
        # In our coordinate system, if we rotate right, kappa should be negative? 
        # Let's standardize: positive = left turn.
        kappa = (dx * ddz - dz * ddx)
        return kappa

    def _find_segments(self, is_corner: np.ndarray, s_grid: np.ndarray) -> List[Tuple[float, float]]:
        """Groups contiguous True values into (start, end) tuples."""
        segments = []
        if not np.any(is_corner): return segments
        
        start_idx = None
        for i in range(len(is_corner)):
            if is_corner[i] and start_idx is None:
                start_idx = i
            elif not is_corner[i] and start_idx is not None:
                segments.append((s_grid[start_idx], s_grid[i]))
                start_idx = None
        
        if start_idx is not None:
            segments.append((s_grid[start_idx], s_grid[-1]))
            
        # Handle wrap-around corners (if first and last points are in a corner)
        if is_corner[0] and is_corner[-1] and len(segments) > 1:
            last_seg = segments.pop()
            first_seg = segments.pop(0)
            segments.insert(0, (last_seg[0], first_seg[1]))
            
        return segments

    def get_corner_at(self, s: float) -> Optional[CornerArchetype]:
        """Returns the corner archetype for a given s position."""
        for corner in self.corners:
            if corner.s_start <= s <= corner.s_end:
                return corner
            # Handle wrap-around
            if corner.s_start > corner.s_end:
                if s >= corner.s_start or s <= corner.s_end:
                    return corner
        return None
