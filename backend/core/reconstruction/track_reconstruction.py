import numpy as np
import logging
from typing import List, Dict, Any, Tuple
from ..telemetry.telemetry_models import TelemetrySample, TrackPoint
from .spline_builder import SplineBuilder
from .geometry_smoothing import GeometrySmoothing
from ..geometry.track_bounds import TrackBoundsGenerator

logger = logging.getLogger(__name__)

class TrackReconstructor:
    def __init__(self, resampling_step: float = 4.0, output_step: float = 2.0, default_width: float = 14.0):
        self.resampling_step = resampling_step
        self.output_step = output_step
        self.default_width = default_width
        self.points: List[np.ndarray] = []
        self.lap_points: Dict[int, List[np.ndarray]] = {}

    def add_telemetry_samples(self, samples: List[TelemetrySample]):
        added = 0
        for sample in samples:
            pos = np.array([sample.worldPositionX, sample.worldPositionZ], dtype=float)
            if not np.isfinite(pos).all():
                continue

            lap_id = int(sample.lap or 0)
            lap_path = self.lap_points.setdefault(lap_id, [])
            if not lap_path or np.linalg.norm(pos - lap_path[-1]) > 0.75:
                lap_path.append(pos)
                added += 1

            if not self.points or np.linalg.norm(pos - self.points[-1]) > 0.75:
                self.points.append(pos)
        return added

    def reset(self):
        self.points = []
        self.lap_points = {}

    @staticmethod
    def _path_length(points: np.ndarray, closed: bool = False) -> float:
        if len(points) < 2:
            return 0.0

        length = float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())
        if closed:
            length += float(np.linalg.norm(points[-1] - points[0]))
        return length

    def _clean_path(self, points: List[np.ndarray]) -> np.ndarray:
        raw_points = np.array(points, dtype=float)
        raw_points = GeometrySmoothing.remove_invalid(raw_points)
        raw_points = GeometrySmoothing.remove_duplicate_points(raw_points, min_spacing=0.75)
        return GeometrySmoothing.remove_distance_outliers(raw_points)

    def _filtered_lap_paths(self) -> List[Tuple[int, np.ndarray, float, float]]:
        candidates: List[Tuple[int, np.ndarray, float, float]] = []
        for lap_id, points in sorted(self.lap_points.items(), key=lambda item: item[0]):
            clean = self._clean_path(points)
            if len(clean) < 50:
                continue

            length = self._path_length(clean, closed=False)
            if length <= 500.0:
                continue

            closure_gap = float(np.linalg.norm(clean[-1] - clean[0]))
            candidates.append((lap_id, clean, length, closure_gap))

        if len(candidates) < 2:
            return candidates

        lengths = np.array([item[2] for item in candidates], dtype=float)
        median_length = float(np.median(lengths))
        max_length_error = max(0.12 * median_length, 250.0)
        max_closure_gap = max(50.0, 0.03 * median_length)

        valid = [
            item for item in candidates
            if abs(item[2] - median_length) <= max_length_error and item[3] <= max_closure_gap
        ]
        return valid if valid else candidates

    @staticmethod
    def _resample_closed_to_count(points: np.ndarray, count: int) -> np.ndarray:
        if len(points) < 2:
            return points

        source = points[:-1] if np.linalg.norm(points[0] - points[-1]) < 1e-6 else points
        source = np.vstack([source, source[0]])
        dists = np.linalg.norm(np.diff(source, axis=0), axis=1)
        accum_dist = np.concatenate([[0.0], np.cumsum(dists)])
        total_length = float(accum_dist[-1])
        if total_length <= 0:
            return source[:1]

        new_distances = np.linspace(0.0, total_length, count, endpoint=False)
        resampled = np.zeros((count, points.shape[1]), dtype=float)
        for axis in range(points.shape[1]):
            resampled[:, axis] = np.interp(new_distances, accum_dist, source[:, axis])
        return resampled

    @staticmethod
    def _align_lap_to_reference(points: np.ndarray, reference: np.ndarray) -> np.ndarray:
        def roll_to_reference(candidate: np.ndarray) -> np.ndarray:
            idx = int(np.argmin(np.linalg.norm(candidate - reference[0], axis=1)))
            return np.roll(candidate, -idx, axis=0)

        forward = roll_to_reference(points)
        reverse = roll_to_reference(points[::-1])
        sample_count = min(len(reference), len(points), 120)
        forward_error = float(np.linalg.norm(forward[:sample_count] - reference[:sample_count], axis=1).mean())
        reverse_error = float(np.linalg.norm(reverse[:sample_count] - reference[:sample_count], axis=1).mean())
        return reverse if reverse_error < forward_error else forward

    def _average_lap_paths(self, lap_paths: List[Tuple[int, np.ndarray, float, float]]) -> Tuple[np.ndarray, Dict[str, Any]]:
        lengths = [item[2] for item in lap_paths]
        median_length = float(np.median(np.array(lengths, dtype=float)))
        target_count = max(256, min(2048, int(median_length / self.resampling_step)))

        resampled_laps = []
        for _, points, _, _ in lap_paths:
            smoothed = GeometrySmoothing.smooth_points(points, window_length=15, polyorder=3)
            resampled_laps.append(self._resample_closed_to_count(smoothed, target_count))

        reference = resampled_laps[0]
        aligned_laps = [reference]
        for lap in resampled_laps[1:]:
            aligned_laps.append(self._align_lap_to_reference(lap, reference))

        averaged = np.mean(np.stack(aligned_laps, axis=0), axis=0)
        averaged = GeometrySmoothing.smooth_points(averaged, window_length=21, polyorder=3)

        return averaged, {
            "method": "multi_lap_average",
            "lapsUsed": len(lap_paths),
            "lapIds": [int(item[0]) for item in lap_paths],
            "lapLengths": [float(item[2]) for item in lap_paths],
            "lapClosureGaps": [float(item[3]) for item in lap_paths],
            "medianLapLength": median_length,
        }

    def _build_open_track_points(self, points: np.ndarray) -> Tuple[List[TrackPoint], float]:
        resampled_points = GeometrySmoothing.resample_evenly(points, self.output_step, closed=False)
        if len(resampled_points) < 2:
            raise ValueError("Open reconstruction requires at least two points")

        segment_lengths = np.linalg.norm(np.diff(resampled_points, axis=0), axis=1)
        distances = np.concatenate([[0.0], np.cumsum(segment_lengths)])
        total_length = max(float(distances[-1]), 1e-6)

        gradients = np.zeros_like(resampled_points)
        gradients[0] = resampled_points[1] - resampled_points[0]
        gradients[-1] = resampled_points[-1] - resampled_points[-2]
        if len(resampled_points) > 2:
            gradients[1:-1] = resampled_points[2:] - resampled_points[:-2]

        mags = np.linalg.norm(gradients, axis=1) + 1e-10
        tangents = gradients / mags[:, None]
        normals = np.column_stack([-tangents[:, 1], tangents[:, 0]])

        curvature = np.zeros(len(resampled_points), dtype=float)
        if len(resampled_points) > 3:
            delta_tangent = np.linalg.norm(np.diff(tangents, axis=0), axis=1)
            delta_distance = np.diff(distances) + 1e-10
            curvature[1:] = delta_tangent / delta_distance

        track_points = []
        for i, point in enumerate(resampled_points):
            track_points.append(TrackPoint(
                x=float(point[0]),
                y=0.0,
                z=float(point[1]),
                distance=float(distances[i]),
                spline_t=float(distances[i] / total_length),
                curvature=float(curvature[i]),
                tangent=(float(tangents[i, 0]), float(tangents[i, 1])),
                normal=(float(normals[i, 0]), float(normals[i, 1])),
            ))

        return track_points, total_length

    def _build_closed_track_points(self, points: np.ndarray) -> Tuple[List[TrackPoint], float]:
        smoothed_points = GeometrySmoothing.smooth_points(points)
        resampled_points = GeometrySmoothing.resample_evenly(smoothed_points, self.resampling_step, closed=True)
        spline_x, spline_z, accum_dist = SplineBuilder.build_closed_spline(resampled_points)

        total_length = float(accum_dist[-1])
        num_output_points = max(64, int(total_length / self.output_step))
        s_vals = np.linspace(0, total_length, num_output_points, endpoint=False)

        x_vals = spline_x(s_vals)
        z_vals = spline_z(s_vals)
        dx = spline_x(s_vals, 1)
        dz = spline_z(s_vals, 1)
        mags = np.hypot(dx, dz) + 1e-10
        tx, tz = dx / mags, dz / mags
        nx, nz = -tz, tx

        ddx = spline_x(s_vals, 2)
        ddz = spline_z(s_vals, 2)
        curvature = (dx * ddz - dz * ddx) / (mags**3)

        track_points = []
        for i in range(num_output_points):
            track_points.append(TrackPoint(
                x=float(x_vals[i]),
                y=0.0,
                z=float(z_vals[i]),
                distance=float(s_vals[i]),
                spline_t=float(s_vals[i] / total_length),
                curvature=float(curvature[i]),
                tangent=(float(tx[i]), float(tz[i])),
                normal=(float(nx[i]), float(nz[i])),
            ))

        return track_points, total_length

    def reconstruct(self, track_name: str = "Unknown Track", closed_loop: bool = True) -> Dict[str, Any]:
        if not closed_loop:
            if len(self.points) < 10:
                return {"error": "Not enough points for reconstruction"}
            raw_points = self._clean_path(self.points)
            reconstruction_meta = {
                "method": "live_open_path",
                "lapsUsed": 0,
                "lapIds": [],
                "lapLengths": [self._path_length(raw_points, closed=False)],
                "lapClosureGaps": [],
                "medianLapLength": self._path_length(raw_points, closed=False),
            }
        else:
            lap_paths = self._filtered_lap_paths()

            if len(lap_paths) >= 2:
                raw_points, reconstruction_meta = self._average_lap_paths(lap_paths)
            elif len(lap_paths) == 1:
                lap_id, raw_points, lap_length, closure_gap = lap_paths[0]
                reconstruction_meta = {
                    "method": "single_lap",
                    "lapsUsed": 1,
                    "lapIds": [int(lap_id)],
                    "lapLengths": [float(lap_length)],
                    "lapClosureGaps": [float(closure_gap)],
                    "medianLapLength": float(lap_length),
                }
            elif len(self.points) >= 10:
                raw_points = self._clean_path(self.points)
                reconstruction_meta = {
                    "method": "single_path",
                    "lapsUsed": 0,
                    "lapIds": [],
                    "lapLengths": [self._path_length(raw_points, closed=False)],
                    "lapClosureGaps": [],
                    "medianLapLength": self._path_length(raw_points, closed=False),
                }
            else:
                return {"error": "Not enough points for reconstruction"}

        raw_points = GeometrySmoothing.remove_invalid(raw_points)
        raw_points = GeometrySmoothing.remove_duplicate_points(raw_points, min_spacing=0.75)
        raw_points = GeometrySmoothing.remove_distance_outliers(raw_points)

        if len(raw_points) < 10:
            return {"error": "Not enough clean points for reconstruction"}

        if closed_loop:
            track_points, total_length = self._build_closed_track_points(raw_points)
        else:
            track_points, total_length = self._build_open_track_points(raw_points)

        bounds = TrackBoundsGenerator.generate_fixed_width_bounds(track_points, self.default_width)

        return {
            "name": track_name,
            "trackName": track_name,
            "track_length": float(total_length),
            "trackLength": float(total_length),
            "length_meters": float(total_length),
            "total_points": len(track_points),
            "closedLoop": bool(closed_loop),
            "centerline": track_points,
            "left_edge": bounds["left"],
            "right_edge": bounds["right"],
            "boundsLeft": bounds["left"],
            "boundsRight": bounds["right"],
            "normals": [{"x": p.normal[0], "z": p.normal[1]} for p in track_points],
            "curvature": [float(p.curvature) for p in track_points],
            "coordinate_system": "world_xz",
            "game_code": "AssettoCorsa",
            "source": "telemetry_reconstruction_multilap" if reconstruction_meta["method"] == "multi_lap_average" else "telemetry_reconstruction",
            "version": 2,
            "reconstruction": reconstruction_meta,
        }
