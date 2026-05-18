import numpy as np
from scipy.spatial import KDTree
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from ..telemetry.telemetry_models import TrackPoint
from .nearest_point import nearest_segment_projection
from .lateral_offset import signed_lateral_offset, tangent_and_normal


@dataclass
class ProjectedCarState:
    world_position: List[float]
    map_position: Dict[str, float]
    projected_world_position: List[float]
    projected_position: Dict[str, float]
    spline_t: float
    lateral_offset: float
    track_heading: List[float]
    distance_along_track: float
    nearest_segment_index: int

class ProjectionEngine:
    def __init__(self, centerline: List[TrackPoint], closed_loop: bool = True):
        self.centerline = centerline
        self.closed_loop = closed_loop
        self.points = np.array([[p.x, p.z] for p in centerline])
        self.distances = np.array([p.distance for p in centerline])
        if closed_loop:
            self.total_length = max(
                centerline[-1].distance + float(np.linalg.norm(self.points[-1] - self.points[0])),
                1e-6,
            )
        else:
            self.total_length = max(float(centerline[-1].distance), 1e-6)
        self.tree = KDTree(self.points)

    def project_car(self, x: float, z: float, previous_s: Optional[float] = None) -> Dict[str, Any]:
        q = np.array([x, z])
        nearest = nearest_segment_projection(
            q,
            self.points,
            self.distances,
            self.total_length,
            tree=self.tree,
            k=10,
            closed_loop=self.closed_loop,
        )

        projected = nearest["projected_point"]
        tangent, normal = tangent_and_normal(nearest["segment_vector"])
        lateral_offset = signed_lateral_offset(q, projected, normal)
        distance_along_track = float(nearest["distance_along_track"])

        state = ProjectedCarState(
            world_position=[float(x), 0.0, float(z)],
            map_position={"x": float(x), "y": float(-z)},
            projected_world_position=[float(projected[0]), 0.0, float(projected[1])],
            projected_position={"x": float(projected[0]), "y": float(-projected[1])},
            spline_t=float(distance_along_track / self.total_length),
            lateral_offset=float(lateral_offset),
            track_heading=[float(tangent[0]), float(-tangent[1])],
            distance_along_track=distance_along_track,
            nearest_segment_index=int(nearest["segment_index"]),
        )

        return {
            "world_position": state.world_position,
            "worldPosition": state.world_position,
            "map_position": state.map_position,
            "mapPosition": state.map_position,
            "projected_world_position": state.projected_world_position,
            "projectedWorldPosition": state.projected_world_position,
            "projected_position": state.projected_position,
            "projectedPosition": state.projected_position,
            "distance_along_track": state.distance_along_track,
            "distanceAlongTrack": state.distance_along_track,
            "spline_t": state.spline_t,
            "p": state.spline_t,
            "lateral_offset": state.lateral_offset,
            "lateralOffset": state.lateral_offset,
            "track_heading": state.track_heading,
            "trackHeading": state.track_heading,
            "nearest_segment_index": state.nearest_segment_index,
            "debug": {
                "nearestSegmentIndex": state.nearest_segment_index,
                "segmentT": float(nearest["segment_t"]),
                "distanceToTrack": float(np.sqrt(nearest["distance_sq"])),
                "tangentVector": {"x": float(tangent[0]), "y": float(-tangent[1])},
                "normalVector": {"x": float(normal[0]), "y": float(-normal[1])},
                "projectionLine": {
                    "from": {"x": state.map_position["x"], "y": state.map_position["y"]},
                    "to": {"x": state.projected_position["x"], "y": state.projected_position["y"]},
                },
            },
        }
