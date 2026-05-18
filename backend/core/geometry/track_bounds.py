import numpy as np
from typing import List, Dict, Any
from ..telemetry.telemetry_models import TrackPoint

class TrackBoundsGenerator:
    @staticmethod
    def generate_fixed_width_bounds(centerline: List[TrackPoint], width: float = 14.0) -> Dict[str, List[Dict[str, float]]]:
        half_width = width / 2.0
        left_bound = []
        right_bound = []
        
        for p in centerline:
            nx, nz = p.normal
            left_bound.append({
                "x": float(p.x + nx * half_width),
                "y": float(p.z + nz * half_width),
                "z": float(p.z + nz * half_width),
            })
            right_bound.append({
                "x": float(p.x - nx * half_width),
                "y": float(p.z - nz * half_width),
                "z": float(p.z - nz * half_width),
            })
            
        return {
            "left": left_bound,
            "right": right_bound
        }
