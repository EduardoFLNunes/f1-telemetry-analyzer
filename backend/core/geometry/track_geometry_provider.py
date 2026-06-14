import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..cache.cache_serializer import CacheSerializer
from ..cache.track_cache import TrackCache
from ..kn5.track_edges_from_surface import build_track_edges_interval_raycast_from_manifest
from ..telemetry.telemetry_models import TrackPoint
from ..track_file_resolver import TrackFileResolver
from .interlagos_track_only_fixed import GEOMETRY_NAME, is_interlagos_track, load_fixed_geometry


logger = logging.getLogger(__name__)


def resolve_geometry_resource_root() -> Path:
    configured = os.getenv("AT_BACKEND_RESOURCE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


@dataclass
class TrackGeometryProviderResult:
    track_name: str
    track_data: Dict[str, Any]
    cache_path: Optional[Path]
    provider: str
    source: str
    from_cache: bool = False


def _safe_fragment(value: Optional[str]) -> str:
    text = (value or "default").strip()
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in text).strip("_") or "default"


def kn5_surface_cache_name(track_name: str, track_config: Optional[str]) -> str:
    return f"{_safe_fragment(track_name)}_{_safe_fragment(track_config)}_kn5_surface_interval_geometry"


def _map_to_world_edge(points: Sequence[Sequence[float]]) -> List[Dict[str, float]]:
    edge = []
    for point in points:
        world_z = -float(point[1])
        edge.append({"x": float(point[0]), "y": world_z, "z": world_z})
    return edge


def _curvature(points: Sequence[Sequence[float]], index: int) -> float:
    if len(points) < 3:
        return 0.0
    prev_point = points[(index - 1) % len(points)]
    point = points[index]
    next_point = points[(index + 1) % len(points)]
    ax, ay = float(point[0]) - float(prev_point[0]), float(point[1]) - float(prev_point[1])
    bx, by = float(next_point[0]) - float(point[0]), float(next_point[1]) - float(point[1])
    len_a = (ax * ax + ay * ay) ** 0.5
    len_b = (bx * bx + by * by) ** 0.5
    if len_a <= 1e-9 or len_b <= 1e-9:
        return 0.0
    cross = ax * by - ay * bx
    dot = max(-1.0, min(1.0, (ax * bx + ay * by) / (len_a * len_b)))
    angle = __import__("math").atan2(cross, dot)
    return float(angle / max((len_a + len_b) * 0.5, 1e-9))


def _distances(points: Sequence[Sequence[float]]) -> Tuple[List[float], float]:
    distances = [0.0]
    for index in range(1, len(points)):
        prev_point = points[index - 1]
        point = points[index]
        dx = float(point[0]) - float(prev_point[0])
        dy = float(point[1]) - float(prev_point[1])
        distances.append(distances[-1] + (dx * dx + dy * dy) ** 0.5)
    if len(points) > 1:
        dx = float(points[0][0]) - float(points[-1][0])
        dy = float(points[0][1]) - float(points[-1][1])
        total_length = distances[-1] + (dx * dx + dy * dy) ** 0.5
    else:
        total_length = 0.0
    return distances, total_length


def _width_stats(widths: Sequence[float]) -> Dict[str, Optional[float]]:
    if not widths:
        return {"min": None, "avg": None, "max": None}
    return {
        "min": round(min(widths), 6),
        "avg": round(sum(widths) / len(widths), 6),
        "max": round(max(widths), 6),
    }


def track_data_from_interval_edges(result: Dict[str, Any], cache_path: Optional[Path] = None) -> Dict[str, Any]:
    samples = [sample for sample in result.get("edges", {}).get("samples", []) if sample.get("centerline")]
    center_map = [sample["centerline"] for sample in samples]
    left_map = [sample["leftEdge"] for sample in samples if sample.get("leftEdge")]
    right_map = [sample["rightEdge"] for sample in samples if sample.get("rightEdge")]
    distances, total_length = _distances(center_map)
    track_length = float(total_length or result.get("metrics", {}).get("trackLength", 0.0))

    centerline: List[TrackPoint] = []
    widths: List[float] = []
    p_values: List[float] = []
    for index, sample in enumerate(samples):
        point = sample["centerline"]
        tangent_map = sample.get("tangent", [1.0, 0.0])
        normal_map = sample.get("normal", [0.0, 1.0])
        spline_t = distances[index] / track_length if track_length > 1e-9 else 0.0
        p_values.append(float(sample.get("index", index)) / max(len(samples) - 1, 1))
        if sample.get("localWidth") is not None:
            widths.append(float(sample["localWidth"]))
        centerline.append(
            TrackPoint(
                x=float(point[0]),
                y=0.0,
                z=-float(point[1]),
                distance=float(distances[index]),
                spline_t=float(spline_t),
                curvature=_curvature(center_map, index),
                tangent=(float(tangent_map[0]), -float(tangent_map[1])),
                normal=(float(normal_map[0]), -float(normal_map[1])),
            )
        )

    bounds = result.get("edges", {}).get("bounds") or {}
    width_stats = _width_stats(widths)
    track_name = result.get("trackName") or "unknown"
    track_config = result.get("trackConfig") or "default"
    metadata = {
        "trackConfig": track_config,
        "surfaceSource": result.get("surfaceSource"),
        "fastLaneAi": result.get("fastLaneAi"),
        "raycastAlgorithm": result.get("raycastAlgorithm"),
        "metrics": result.get("metrics", {}),
        "widthStats": width_stats,
        "bounds": bounds,
        "cachePath": str(cache_path) if cache_path else None,
    }

    return {
        "name": track_name,
        "trackName": track_name,
        "trackConfig": track_config,
        "trackLength": track_length,
        "track_length": track_length,
        "length_meters": track_length,
        "version": 1,
        "source": "assetto_corsa_track_files",
        "provider": "kn5_surface_interval",
        "providerSource": "assetto_corsa_track_files",
        "cachePath": str(cache_path) if cache_path else None,
        "coordinateSystem": "world_xz",
        "closedLoop": True,
        "generatedAt": datetime.utcnow().isoformat(),
        "reconstruction": {
            "method": "kn5_surface_interval",
            "provider": "kn5_surface_interval",
            "source": "assetto_corsa_track_files",
        },
        "centerline": centerline,
        "boundsLeft": _map_to_world_edge(left_map),
        "boundsRight": _map_to_world_edge(right_map),
        "left_edge": _map_to_world_edge(left_map),
        "right_edge": _map_to_world_edge(right_map),
        "localWidth": widths,
        "widthMin": width_stats["min"],
        "widthAvg": width_stats["avg"],
        "widthMax": width_stats["max"],
        "tangent": [{"x": p.tangent[0], "z": p.tangent[1]} for p in centerline],
        "normal": [{"x": p.normal[0], "z": p.normal[1]} for p in centerline],
        "normals": [{"x": p.normal[0], "z": p.normal[1]} for p in centerline],
        "p": p_values,
        "bounds": bounds,
        "metadata": metadata,
    }


class Kn5SurfaceTrackGeometryProvider:
    provider = "kn5_surface_interval"
    source = "assetto_corsa_track_files"

    def __init__(self, cache: TrackCache, ac_root: Optional[str] = None):
        self.cache = cache
        self.ac_root = ac_root

    def load_or_build(
        self,
        track_name: str,
        track_config: Optional[str],
        *,
        source: str = "assetto_corsa",
        game_code: str = "assetto_corsa",
    ) -> Optional[TrackGeometryProviderResult]:
        resource_root = resolve_geometry_resource_root()
        if is_interlagos_track(track_name, track_config):
            fixed = load_fixed_geometry(resource_root)
            if fixed:
                fixed_provider = fixed.get("provider") or GEOMETRY_NAME
                fixed_path = Path(
                    fixed.get("cachePath")
                    or resource_root / "data" / "debug" / "interlagos_track_only_fixed_geometry.json"
                )
                return TrackGeometryProviderResult(
                    f"vhe_interlagos_gp_{_safe_fragment(fixed_provider)}",
                    fixed,
                    fixed_path,
                    fixed_provider,
                    self.source,
                    from_cache=True,
                )

        cache_name = kn5_surface_cache_name(track_name, track_config)
        cache_path = self.cache.cache_dir / f"{self.cache._safe_name(cache_name)}.json"
        cached = self.cache.load_track(cache_name)
        if cached and cached.get("provider") == self.provider:
            cached["cachePath"] = str(cache_path)
            cached.setdefault("metadata", {})["cachePath"] = str(cache_path)
            return TrackGeometryProviderResult(cache_name, cached, cache_path, self.provider, self.source, from_cache=True)

        resolver = TrackFileResolver(ac_root=self.ac_root)
        manifest = resolver.build_track_file_manifest(
            track_name,
            track_config,
            source=source,
            game_code=game_code,
        )
        manifest_dict = manifest.to_dict()
        if not (manifest_dict.get("candidateGeometryFiles") or {}).get("mainVisual"):
            logger.warning("KN5 provider skipped: missing main visual KN5 for %s/%s", track_name, track_config)
            return None
        if not (manifest_dict.get("aiFiles") or {}).get("fast_lane"):
            logger.warning("KN5 provider skipped: missing fast_lane.ai for %s/%s", track_name, track_config)
            return None

        result = build_track_edges_interval_raycast_from_manifest(manifest_dict)
        metrics = result.get("metrics", {})
        if metrics.get("validRaycastSamples", 0) <= 0 or not metrics.get("loopClosed"):
            logger.warning("KN5 provider skipped: interval raycast validation failed: %s", metrics)
            return None

        track_data = track_data_from_interval_edges(result, cache_path=cache_path)
        self.cache.save_track(cache_name, track_data)
        track_data["cachePath"] = str(cache_path)
        track_data.setdefault("metadata", {})["cachePath"] = str(cache_path)
        return TrackGeometryProviderResult(cache_name, track_data, cache_path, self.provider, self.source, from_cache=False)


class CacheTrackGeometryProvider:
    provider = "cache"
    source = "track_cache"

    def __init__(self, cache: TrackCache):
        self.cache = cache

    def load(self, cache_name: str) -> Optional[TrackGeometryProviderResult]:
        cached = self.cache.load_track(cache_name)
        if not cached:
            return None
        path = self.cache.cache_dir / f"{self.cache._safe_name(cache_name)}.json"
        cached["provider"] = cached.get("provider", "cache")
        cached["providerSource"] = cached.get("providerSource", "track_cache")
        cached["cachePath"] = str(path)
        cached.setdefault("metadata", {})["cachePath"] = str(path)
        return TrackGeometryProviderResult(cache_name, cached, path, cached["provider"], cached["providerSource"], from_cache=True)


class DebugTrajectoryTrackGeometryProvider:
    provider = "debug_trajectory"
    source = "driver_trajectory_debug"

    @staticmethod
    def enabled() -> bool:
        return os.getenv("DEBUG_ALLOW_TRAJECTORY_TRACK", "false").strip().lower() in {"1", "true", "yes", "on"}
