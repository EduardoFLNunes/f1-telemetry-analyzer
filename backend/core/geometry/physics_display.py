import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
from scipy.interpolate import interp1d
from ..telemetry.telemetry_models import TrackPoint

Point = List[float]

def _round(value: float) -> float:
    return round(float(value), 6)

def _point(point: Sequence[float]) -> Point:
    return [_round(point[0]), _round(point[1])]

def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))

def circular_smooth(points: np.ndarray, window: int) -> np.ndarray:
    if len(points) < 3 or window <= 1:
        return points
    if window % 2 == 0:
        window += 1
    radius = window // 2
    count = len(points)
    
    # Simple moving average for points (Nx2)
    smoothed = np.zeros_like(points)
    for i in range(count):
        indices = np.arange(i - radius, i + radius + 1) % count
        smoothed[i] = np.mean(points[indices], axis=0)
    return smoothed

def smooth_values(values: np.ndarray, window: int) -> np.ndarray:
    if len(values) < 3 or window <= 1:
        return values
    if window % 2 == 0:
        window += 1
    radius = window // 2
    count = len(values)
    smoothed = np.zeros_like(values)
    for i in range(count):
        indices = np.arange(i - radius, i + radius + 1) % count
        smoothed[i] = np.mean(values[indices])
    return smoothed

def detect_and_repair_deformations(points: np.ndarray, window: int = 10, threshold: float = 0.2, max_repair: float = 0.5) -> np.ndarray:
    """
    Detects short-wave deformations and applies local repairs.
    points: Nx2 array
    """
    count = len(points)
    if count < window * 2: return points
    
    repaired = points.copy()
    repaired_indices = []
    
    # 1. Detect
    # Compare local direction (points[i] - points[i-1]) with trend
    # Trend is average of neighbors in a larger window
    for i in range(count):
        # Local tangent
        p_prev = points[(i - 1) % count]
        p_curr = points[i]
        local_dir = p_curr - p_prev
        local_dir /= (np.linalg.norm(local_dir) + 1e-9)
        
        # Trend tangent
        trend_prev = points[(i - window) % count]
        trend_next = points[(i + window) % count]
        trend_dir = trend_next - trend_prev
        trend_dir /= (np.linalg.norm(trend_dir) + 1e-9)
        
        # Deviation
        dot = np.dot(local_dir, trend_dir)
        if dot < 0.7: # Significant deviation
            repaired_indices.append(i)
            
    # 2. Repair (simple local spline-like averaging for detected indices)
    # Using a simple weighted average of neighbors, limited to max_repair
    for idx in repaired_indices:
        neighbors = [repaired[(idx - 2) % count], repaired[(idx - 1) % count], 
                     repaired[(idx + 1) % count], repaired[(idx + 2) % count]]
        target = np.mean(neighbors, axis=0)
        
        disp = target - repaired[idx]
        if np.linalg.norm(disp) > max_repair:
            disp = disp / np.linalg.norm(disp) * max_repair
            
        repaired[idx] = repaired[idx] + disp
        
    return repaired, repaired_indices

def generate_physics_display_geometry(
    auth_centerline: List[TrackPoint],
    auth_widths: List[float],
    target_spacing: float = 1.0,
    smoothing_window: int = 21,
    width_smoothing_window: int = 31,
    max_displacement: float = 0.5
) -> Dict[str, Any]:
    """
    Generates a smoothed version of the physics geometry for display only.
    """
    if not auth_centerline:
        return {}

    # 1. Prepare authoritative data (map space: x, -z)
    raw_points = np.array([[p.x, -p.z] for p in auth_centerline])
    raw_distances = np.array([p.distance for p in auth_centerline])
    raw_widths = np.array(auth_widths)
    total_length = auth_centerline[-1].distance + _distance([auth_centerline[-1].x, -auth_centerline[-1].z], [auth_centerline[0].x, -auth_centerline[0].z])

    # 2. Resample onto uniform grid
    n_points = int(total_length / target_spacing)
    if n_points < 10: n_points = 10
    
    s_target = np.linspace(0, total_length, n_points, endpoint=False)
    
    # Interpolation functions (cubic for centerline, linear for width)
    _, unique_idx = np.unique(raw_distances, return_index=True)
    u_distances = raw_distances[unique_idx]
    u_points = raw_points[unique_idx]
    u_widths = raw_widths[unique_idx]
    
    # Pad for periodic interpolation
    p_distances = np.concatenate([u_distances - total_length, u_distances, u_distances + total_length])
    p_points = np.concatenate([u_points, u_points, u_points])
    p_widths = np.concatenate([u_widths, u_widths, u_widths])
    
    f_x = interp1d(p_distances, p_points[:, 0], kind='cubic')
    f_y = interp1d(p_distances, p_points[:, 1], kind='cubic')
    f_w = interp1d(p_distances, p_widths, kind='linear')
    
    resampled_points = np.column_stack([f_x(s_target), f_y(s_target)])
    resampled_widths = f_w(s_target)
    
    # 3. Local Repair (S-curve removal)
    repaired_points, repaired_idx = detect_and_repair_deformations(resampled_points, window=10, max_repair=0.5)

    # 4. Smoothing
    smoothed_points = circular_smooth(repaired_points, smoothing_window)
    smoothed_widths = smooth_values(resampled_widths, width_smoothing_window)
    
    # 5. Constraint: max displacement from authoritative
    raw_at_target = np.column_stack([f_x(s_target), f_y(s_target)])
    displacements = np.linalg.norm(smoothed_points - raw_at_target, axis=1)
    
    for i in range(len(smoothed_points)):
        if displacements[i] > max_displacement:
            direction = smoothed_points[i] - raw_at_target[i]
            direction = direction / displacements[i]
            smoothed_points[i] = raw_at_target[i] + direction * max_displacement

    # 6. Reconstruct edges
    count = len(smoothed_points)
    display_centerline = []
    display_left = []
    display_right = []
    
    for i in range(count):
        p_prev = smoothed_points[(i - 1) % count]
        p_next = smoothed_points[(i + 1) % count]
        
        dx = p_next[0] - p_prev[0]
        dy = p_next[1] - p_prev[1]
        length = math.hypot(dx, dy)
        
        if length > 1e-9:
            tx, ty = dx / length, dy / length
        else:
            tx, ty = 1.0, 0.0
            
        nx, ny = -ty, tx
        half_w = smoothed_widths[i] * 0.5
        
        p = smoothed_points[i]
        
        display_centerline.append({"x": _round(p[0]), "y": _round(-p[1])})
        display_left.append({"x": _round(p[0] + nx * half_w), "y": _round(-(p[1] + ny * half_w))})
        display_right.append({"x": _round(p[0] - nx * half_w), "y": _round(-(p[1] - ny * half_w))})

    return {
        "centerline": display_centerline,
        "leftEdge": display_left,
        "rightEdge": display_right,
        "width": [float(w) for w in smoothed_widths],
        "visualOnly": True,
        "source": "track_physics_geometry_smoothed_display",
        "basedOnPhysics": True,
        "metadata": {
            "targetSpacing": target_spacing,
            "smoothingWindow": smoothing_window,
            "widthSmoothingWindow": width_smoothing_window,
            "maxDisplacement": max_displacement,
            "displayLocalRepairEnabled": True,
            "displayLocalRepairsApplied": len(repaired_idx),
            "maxDisplayRepairDisplacement": 0.5
        }
    }

def calculate_physics_display_metrics(raw_track: Dict[str, Any], display_track: Dict[str, Any]) -> Dict[str, Any]:
    raw_center = [[p.x, -p.z] for p in raw_track.get("centerline", [])]
    display_center = [[p["x"], p["y"]] for p in display_track.get("centerline", [])]
    
    raw_segments = [math.hypot(raw_center[i][0] - raw_center[i-1][0], raw_center[i][1] - raw_center[i-1][1]) for i in range(1, len(raw_center))]
    display_segments = [math.hypot(display_center[i][0] - display_center[i-1][0], display_center[i][1] - display_center[i-1][1]) for i in range(1, len(display_center))]

    raw_widths = raw_track.get("localWidth", [])
    display_widths = display_track.get("width", [])

    return {
        "rawPointCount": len(raw_center),
        "displayPointCount": len(display_center),
        "rawMaxSegmentLength": _round(max(raw_segments)) if raw_segments else 0,
        "displayMaxSegmentLength": _round(max(display_segments)) if display_segments else 0,
        "widthRaw": {
            "min": _round(min(raw_widths)) if raw_widths else 0,
            "avg": _round(sum(raw_widths)/len(raw_widths)) if raw_widths else 0,
            "max": _round(max(raw_widths)) if raw_widths else 0
        },
        "widthDisplay": {
            "min": _round(min(display_widths)) if display_widths else 0,
            "avg": _round(sum(display_widths)/len(display_widths)) if display_widths else 0,
            "max": _round(max(display_widths)) if display_widths else 0
        }
    }
