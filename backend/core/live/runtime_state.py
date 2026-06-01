from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from ..car_physics import build_player_car_physics
from ..telemetry.telemetry_models import TelemetrySample, TrackPoint
from ..projection.spatial_projection import ProjectionEngine
from ..cache.cache_serializer import CacheSerializer
from .lap_collector import TrackBuildState

@dataclass
class RuntimeState:
    current_track_name: Optional[str] = None
    track_data: Optional[Dict[str, Any]] = None
    projection_engine: Optional[ProjectionEngine] = None
    api_track_cache: Optional[Dict[str, Any]] = None
    last_sample: Optional[TelemetrySample] = None
    car_projected_state: Optional[Dict[str, Any]] = None
    last_distance_along_track: Optional[float] = None
    track_build_state: TrackBuildState = TrackBuildState.NO_TRACK
    build_method: str = "none"
    lap_complete: bool = False
    
    def update_track(self, name: str, data: Dict[str, Any]):
        self.current_track_name = name
        self.track_data = data
        self.api_track_cache = CacheSerializer.to_api_track(data)
        self.projection_engine = ProjectionEngine(data["centerline"], closed_loop=bool(data.get("closedLoop", True)))
        self.track_build_state = TrackBuildState.TRACK_READY
        self.build_method = data.get("reconstruction", {}).get("method", "cached_closed_loop")

    def update_car(self, sample: TelemetrySample):
        self.last_sample = sample
        if self.projection_engine:
            proj = self.projection_engine.project_car(
                sample.worldPositionX,
                sample.worldPositionZ,
                previous_s=self.last_distance_along_track,
            )
            self.last_distance_along_track = proj["distanceAlongTrack"]

            projected = proj["projectedPosition"]
            projected_world = proj["projectedWorldPosition"]
            map_position = proj["mapPosition"]
            drift = ((sample.worldPositionX - projected_world[0]) ** 2 + (sample.worldPositionZ - projected_world[2]) ** 2) ** 0.5
            speed_mps = sample.speed / 3.6

            self.car_projected_state = {
                "carId": sample.carId,
                "worldPosition": sample.worldPosition,
                "mapPosition": map_position,
                "projectedWorldPosition": projected_world,
                "projectedPosition": projected,
                "spline_t": proj["spline_t"],
                "p": proj["p"],
                "distanceAlongTrack": proj["distanceAlongTrack"],
                "lateralOffset": proj["lateralOffset"],
                "lateral_offset": proj["lateralOffset"],
                "heading": sample.yaw,
                "speedKmh": sample.speed,
                "speed": speed_mps,
                "throttle": sample.throttle,
                "brake": sample.brake,
                "steering": sample.steering,
                "gear": sample.gear,
                "rpm": sample.rpm,
                "lap": sample.lap,
                "lap_number": sample.lap,
                "sector": sample.sector,
                "sessionTime": sample.sessionTime,
                "trackHeading": proj["trackHeading"],
                "world_x": sample.worldPositionX,
                "world_y": sample.worldPositionY,
                "world_z": sample.worldPositionZ,
                "x": map_position["x"],
                "y": map_position["y"],
                "z": map_position["y"],
                "projected_x": projected["x"],
                "projected_y": projected["y"],
                "projected_z": projected["y"],
                "s": proj["distanceAlongTrack"],
                "L": proj["lateralOffset"],
                "dx": map_position["x"] - projected["x"],
                "dy": map_position["y"] - projected["y"],
                "dz": map_position["y"] - projected["y"],
                "alignment_drift": drift,
                "accel_g": {"x": sample.accelX, "y": sample.accelY, "z": sample.accelZ},
                "carPhysics": build_player_car_physics(sample),
                "delta": 0.0,
                "timestamp": sample.timestamp_ms,
                "projectionDebug": proj["debug"],
            }
        else:
            self.car_projected_state = {
                "carId": sample.carId,
                "worldPosition": sample.worldPosition,
                "mapPosition": {"x": sample.worldPositionX, "y": -sample.worldPositionZ},
                "projectedWorldPosition": None,
                "projectedPosition": None,
                "distanceAlongTrack": None,
                "lateralOffset": None,
                "lateral_offset": None,
                "speedKmh": sample.speed,
                "speed": sample.speed / 3.6,
                "lap": sample.lap,
                "sessionTime": sample.sessionTime,
                "heading": sample.yaw,
                "world_x": sample.worldPositionX,
                "world_y": sample.worldPositionY,
                "world_z": sample.worldPositionZ,
                "x": sample.worldPositionX,
                "y": -sample.worldPositionZ,
                "z": -sample.worldPositionZ,
                "s": 0.0,
                "L": None,
                "alignment_drift": None,
                "accel_g": {"x": sample.accelX, "y": sample.accelY, "z": sample.accelZ},
                "carPhysics": build_player_car_physics(sample),
                "delta": 0.0,
                "timestamp": sample.timestamp_ms,
            }

        return self.car_projected_state

    def api_track(self) -> Optional[Dict[str, Any]]:
        if not self.track_data:
            return None
        if not self.api_track_cache:
            self.api_track_cache = CacheSerializer.to_api_track(self.track_data)
        return self.api_track_cache
