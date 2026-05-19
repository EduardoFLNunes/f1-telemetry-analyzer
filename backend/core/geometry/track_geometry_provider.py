import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..cache.cache_serializer import CacheSerializer
from ..cache.track_cache import TrackCache
from .track_geometry_cleanup import DEFAULT_CONFIG as CLEANUP_DEFAULT_CONFIG
from .track_geometry_cleanup import audit_geometry, cleanup_geometry, segment_lengths
from .track_visual_geometry import DEFAULT_VISUAL_CONFIG, VISUAL_GEOMETRY_VERSION, TrackVisualGeometryBuilder
from ..kn5.track_edges_from_surface import build_track_edges_interval_raycast_from_manifest
from ..telemetry.telemetry_models import TrackPoint
from ..track_file_resolver import TrackFileResolver


logger = logging.getLogger(__name__)


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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using %.3f", name, raw, default)
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using %d", name, raw, default)
        return default


def track_geometry_cleanup_enabled() -> bool:
    return _env_bool("TRACK_GEOMETRY_CLEANUP_ENABLED", True)


def track_geometry_cleanup_config() -> Dict[str, Any]:
    return {
        "targetSpacingMeters": _env_float(
            "TRACK_GEOMETRY_TARGET_SPACING",
            float(CLEANUP_DEFAULT_CONFIG["targetSpacingMeters"]),
        ),
        "smoothingWindow": _env_int(
            "TRACK_GEOMETRY_SMOOTHING_WINDOW",
            int(CLEANUP_DEFAULT_CONFIG["smoothingWindow"]),
        ),
    }


def track_visual_geometry_enabled() -> bool:
    return _env_bool("TRACK_VISUAL_GEOMETRY_ENABLED", True)


def track_visual_geometry_config() -> Dict[str, Any]:
    visual_surfaces_raw = os.getenv("TRACK_VISUAL_SURFACES", ",".join(DEFAULT_VISUAL_CONFIG["visualSurfaces"]))
    visual_surfaces = [item.strip().upper() for item in visual_surfaces_raw.split(",") if item.strip()]
    return {
        "enabled": track_visual_geometry_enabled(),
        "useRoadOnly": _env_bool("TRACK_VISUAL_USE_ROAD_ONLY", False),
        "visualSurfaces": visual_surfaces or list(DEFAULT_VISUAL_CONFIG["visualSurfaces"]),
        "artifactFixEnabled": _env_bool(
            "TRACK_VISUAL_ARTIFACT_FIX_ENABLED",
            bool(DEFAULT_VISUAL_CONFIG["artifactFixEnabled"]),
        ),
        "widthMedianWindow": _env_int(
            "TRACK_VISUAL_WIDTH_MEDIAN_WINDOW",
            int(DEFAULT_VISUAL_CONFIG["widthMedianWindow"]),
        ),
        "widthSmoothingWindow": _env_int(
            "TRACK_VISUAL_WIDTH_SMOOTHING_WINDOW",
            int(DEFAULT_VISUAL_CONFIG["widthSmoothingWindow"]),
        ),
        "maxWidthDeltaPerSample": _env_float(
            "TRACK_VISUAL_MAX_WIDTH_DELTA_PER_SAMPLE",
            float(DEFAULT_VISUAL_CONFIG["maxWidthDeltaPerSample"]),
        ),
        "minWidth": _env_float(
            "TRACK_VISUAL_MIN_WIDTH",
            float(DEFAULT_VISUAL_CONFIG["minWidth"]),
        ),
        "maxWidth": _env_float(
            "TRACK_VISUAL_MAX_WIDTH",
            float(DEFAULT_VISUAL_CONFIG["maxWidth"]),
        ),
        "artifactWidthMedianWindow": _env_int(
            "TRACK_VISUAL_ARTIFACT_WIDTH_MEDIAN_WINDOW",
            int(DEFAULT_VISUAL_CONFIG["artifactWidthMedianWindow"]),
        ),
        "artifactWidthSmoothingWindow": _env_int(
            "TRACK_VISUAL_ARTIFACT_WIDTH_SMOOTHING_WINDOW",
            int(DEFAULT_VISUAL_CONFIG["artifactWidthSmoothingWindow"]),
        ),
        "centerlineSmoothingWindow": _env_int(
            "TRACK_VISUAL_CENTERLINE_SMOOTHING_WINDOW",
            int(DEFAULT_VISUAL_CONFIG["centerlineSmoothingWindow"]),
        ),
        "normalSmoothingWindow": _env_int(
            "TRACK_VISUAL_NORMAL_SMOOTHING_WINDOW",
            int(DEFAULT_VISUAL_CONFIG["normalSmoothingWindow"]),
        ),
        "edgeSmoothingWindow": _env_int(
            "TRACK_VISUAL_EDGE_SMOOTHING_WINDOW",
            int(DEFAULT_VISUAL_CONFIG["edgeSmoothingWindow"]),
        ),
        "artifactRepairRadius": _env_int(
            "TRACK_VISUAL_ARTIFACT_REPAIR_RADIUS",
            int(DEFAULT_VISUAL_CONFIG["artifactRepairRadius"]),
        ),
        "angleSpikeRadians": _env_float(
            "TRACK_VISUAL_ANGLE_SPIKE_RADIANS",
            float(DEFAULT_VISUAL_CONFIG["angleSpikeRadians"]),
        ),
        "falseCurveAngleRadians": _env_float(
            "TRACK_VISUAL_FALSE_CURVE_ANGLE_RADIANS",
            float(DEFAULT_VISUAL_CONFIG["falseCurveAngleRadians"]),
        ),
        "falseCurveCenterlineAngleRadians": _env_float(
            "TRACK_VISUAL_FALSE_CURVE_CENTERLINE_ANGLE_RADIANS",
            float(DEFAULT_VISUAL_CONFIG["falseCurveCenterlineAngleRadians"]),
        ),
        "falseCurveDeviationMeters": _env_float(
            "TRACK_VISUAL_FALSE_CURVE_DEVIATION_METERS",
            float(DEFAULT_VISUAL_CONFIG["falseCurveDeviationMeters"]),
        ),
        "segmentSpikeMultiplier": _env_float(
            "TRACK_VISUAL_SEGMENT_SPIKE_MULTIPLIER",
            float(DEFAULT_VISUAL_CONFIG["segmentSpikeMultiplier"]),
        ),
    }


def kn5_surface_cache_name(track_name: str, track_config: Optional[str], *, cleaned: bool = False) -> str:
    suffix = "kn5_surface_interval_cleaned_geometry" if cleaned else "kn5_surface_interval_geometry"
    return f"{_safe_fragment(track_name)}_{_safe_fragment(track_config)}_{suffix}"


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


def _map_bounds(*series: Sequence[Sequence[float]]) -> Dict[str, float]:
    points = [point for points in series for point in points]
    if not points:
        return {}
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return {
        "minX": round(min(xs), 6),
        "maxX": round(max(xs), 6),
        "minY": round(min(ys), 6),
        "maxY": round(max(ys), 6),
        "width": round(max(xs) - min(xs), 6),
        "height": round(max(ys) - min(ys), 6),
    }


def _max_segment_length(points: Sequence[Sequence[float]]) -> Optional[float]:
    segments = segment_lengths(points, closed_loop=True)
    if not segments:
        return None
    return round(max(float(segment["length"]) for segment in segments), 6)


def _track_data_from_map_geometry(
    *,
    track_name: str,
    track_config: str,
    center_map: Sequence[Sequence[float]],
    left_map: Sequence[Sequence[float]],
    right_map: Sequence[Sequence[float]],
    widths: Sequence[float],
    cache_path: Optional[Path],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    distances, total_length = _distances(center_map)
    track_length = float(total_length)

    centerline: List[TrackPoint] = []
    p_values: List[float] = []
    for index, point in enumerate(center_map):
        if len(center_map) > 1:
            prev_point = center_map[(index - 1) % len(center_map)]
            next_point = center_map[(index + 1) % len(center_map)]
            tx = float(next_point[0]) - float(prev_point[0])
            ty = float(next_point[1]) - float(prev_point[1])
            tangent_len = (tx * tx + ty * ty) ** 0.5
            if tangent_len > 1e-9:
                tangent_map = [tx / tangent_len, ty / tangent_len]
            else:
                tangent_map = [1.0, 0.0]
        else:
            tangent_map = [1.0, 0.0]
        normal_map = [-float(tangent_map[1]), float(tangent_map[0])]
        spline_t = distances[index] / track_length if track_length > 1e-9 else 0.0
        p_values.append(float(spline_t))
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

    bounds = _map_bounds(center_map, left_map, right_map)
    width_stats = _width_stats(widths)
    metadata = {**metadata, "widthStats": width_stats, "bounds": bounds, "cachePath": str(cache_path) if cache_path else None}

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
        "geometrySource": "assetto_corsa_track_files",
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


def track_data_from_interval_edges(result: Dict[str, Any], cache_path: Optional[Path] = None) -> Dict[str, Any]:
    samples = [sample for sample in result.get("edges", {}).get("samples", []) if sample.get("centerline")]
    center_map = [sample["centerline"] for sample in samples]
    left_map = [sample["leftEdge"] for sample in samples if sample.get("leftEdge")]
    right_map = [sample["rightEdge"] for sample in samples if sample.get("rightEdge")]
    widths = [float(sample["localWidth"]) for sample in samples if sample.get("localWidth") is not None]
    track_name = result.get("trackName") or "unknown"
    track_config = result.get("trackConfig") or "default"
    metadata = {
        "trackConfig": track_config,
        "surfaceSource": result.get("surfaceSource"),
        "fastLaneAi": result.get("fastLaneAi"),
        "raycastAlgorithm": result.get("raycastAlgorithm"),
        "metrics": result.get("metrics", {}),
        "bounds": result.get("edges", {}).get("bounds") or {},
        "cleanupEnabled": False,
        "rawPointCount": len(center_map),
        "cleanedPointCount": len(center_map),
        "rawMaxSegmentLength": _max_segment_length(center_map),
        "cleanedMaxSegmentLength": _max_segment_length(center_map),
    }
    return _track_data_from_map_geometry(
        track_name=track_name,
        track_config=track_config,
        center_map=center_map,
        left_map=left_map,
        right_map=right_map,
        widths=widths,
        cache_path=cache_path,
        metadata=metadata,
    )


def apply_kn5_geometry_cleanup(track_data: Dict[str, Any], *, target_spacing: float, smoothing_window: int) -> Dict[str, Any]:
    center_map = [[float(point.x), -float(point.z)] for point in track_data.get("centerline", [])]
    left_map = [[float(point["x"]), -float(point.get("z", point.get("y", 0.0)))] for point in track_data.get("boundsLeft", [])]
    right_map = [[float(point["x"]), -float(point.get("z", point.get("y", 0.0)))] for point in track_data.get("boundsRight", [])]
    widths = [float(width) for width in track_data.get("localWidth", [])]
    config = {
        "targetSpacingMeters": target_spacing,
        "smoothingWindow": smoothing_window,
    }
    raw_quality = audit_geometry(center_map, left_map, right_map, widths, config=config)
    cleaned = cleanup_geometry(center_map, left_map, right_map, widths, config=config)
    cleaned_quality = audit_geometry(cleaned["centerline"], cleaned["leftEdge"], cleaned["rightEdge"], cleaned["localWidth"], config=config)

    metadata = {
        **track_data.get("metadata", {}),
        "cleanupEnabled": True,
        "cleanupStage": "post_provider_resample_smooth",
        "targetSpacing": target_spacing,
        "targetSpacingMeters": target_spacing,
        "smoothingWindow": smoothing_window,
        "rawPointCount": len(center_map),
        "cleanedPointCount": len(cleaned["centerline"]),
        "rawMaxSegmentLength": _max_segment_length(center_map),
        "cleanedMaxSegmentLength": _max_segment_length(cleaned["centerline"]),
        "rawQuality": raw_quality,
        "cleanedQuality": cleaned_quality,
        "cleanupDetails": cleaned.get("metadata", {}),
    }
    cleaned_track = _track_data_from_map_geometry(
        track_name=track_data.get("trackName", track_data.get("name", "unknown")),
        track_config=track_data.get("trackConfig", "default"),
        center_map=cleaned["centerline"],
        left_map=cleaned["leftEdge"],
        right_map=cleaned["rightEdge"],
        widths=cleaned["localWidth"],
        cache_path=Path(track_data["cachePath"]) if track_data.get("cachePath") else None,
        metadata=metadata,
    )
    cleaned_track["generatedAt"] = track_data.get("generatedAt", cleaned_track["generatedAt"])
    cleaned_track["reconstruction"] = {
        **track_data.get("reconstruction", {}),
        "method": "kn5_surface_interval",
        "provider": "kn5_surface_interval",
        "source": "assetto_corsa_track_files",
        "cleanupEnabled": True,
    }
    cleaned_track["rawPointCount"] = metadata["rawPointCount"]
    cleaned_track["cleanedPointCount"] = metadata["cleanedPointCount"]
    cleaned_track["rawMaxSegmentLength"] = metadata["rawMaxSegmentLength"]
    cleaned_track["cleanedMaxSegmentLength"] = metadata["cleanedMaxSegmentLength"]
    cleaned_track["cleanupEnabled"] = True
    cleaned_track["targetSpacing"] = target_spacing
    cleaned_track["smoothingWindow"] = smoothing_window
    return cleaned_track


def apply_track_visual_geometry(
    track_data: Dict[str, Any],
    *,
    config: Optional[Dict[str, Any]] = None,
    visual_reference_track: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = track_visual_geometry_config()
    if config:
        cfg.update(config)
    if not cfg.get("enabled", True):
        track_data.setdefault("metadata", {})["visualGeometryEnabled"] = False
        return track_data

    visual_source_track = visual_reference_track or track_data
    if visual_reference_track:
        cfg["visualSource"] = "road_only"

    center_map = [[float(point.x), -float(point.z)] for point in visual_source_track.get("centerline", [])]
    left_map = [[float(point["x"]), -float(point.get("z", point.get("y", 0.0)))] for point in visual_source_track.get("boundsLeft", [])]
    right_map = [[float(point["x"]), -float(point.get("z", point.get("y", 0.0)))] for point in visual_source_track.get("boundsRight", [])]
    widths = [float(width) for width in visual_source_track.get("localWidth", [])]
    p_values = [float(value) for value in visual_source_track.get("p", [])] or [index / max(len(center_map) - 1, 1) for index in range(len(center_map))]
    if not center_map or len(center_map) != len(left_map) or len(center_map) != len(right_map) or len(center_map) != len(widths):
        logger.warning("Visual geometry skipped: inconsistent point counts")
        track_data.setdefault("metadata", {})["visualGeometryEnabled"] = False
        track_data.setdefault("metadata", {})["visualGeometryError"] = "inconsistent_point_counts"
        return track_data

    builder = TrackVisualGeometryBuilder(cfg)
    visual_geometry = builder.build(center_map, left_map, right_map, widths, p_values)
    track_data["visualGeometry"] = visual_geometry
    metadata = track_data.setdefault("metadata", {})
    metadata["visualGeometryEnabled"] = True
    metadata["visualGeometrySource"] = visual_geometry["source"]
    metadata["visualSource"] = visual_geometry.get("visualSource")
    metadata["visualArtifactFixEnabled"] = visual_geometry.get("visualArtifactFixEnabled")
    metadata["falseCurveArtifactsRemoved"] = visual_geometry.get("falseCurveArtifactsRemoved")
    metadata["visualWidthStats"] = {
        "min": visual_geometry.get("widthMin"),
        "avg": visual_geometry.get("widthAvg"),
        "max": visual_geometry.get("widthMax"),
    }
    metadata["visualArtifactCount"] = (
        visual_geometry.get("artifactReport", {}).get("artifactCount")
    )
    metadata["visualArtifactCountAfterBuild"] = (
        visual_geometry.get("visualArtifactReport", {}).get("artifactCount")
    )
    return track_data


def build_visual_reference_track_from_manifest(
    manifest: Dict[str, Any],
    *,
    visual_config: Dict[str, Any],
    target_spacing: float,
    smoothing_window: int,
) -> Optional[Dict[str, Any]]:
    surfaces = visual_config.get("visualSurfaces") or ["ROAD"]
    try:
        result = build_track_edges_interval_raycast_from_manifest(
            manifest,
            included_surfaces=surfaces,
        )
        metrics = result.get("metrics", {})
        if metrics.get("validRaycastSamples", 0) <= 0 or not metrics.get("loopClosed"):
            logger.warning("ROAD-only visual reference skipped: invalid raycast metrics: %s", metrics)
            return None
        reference = track_data_from_interval_edges(result, cache_path=None)
        reference.setdefault("metadata", {})["visualReferenceOnly"] = True
        reference.setdefault("metadata", {})["visualSurfaces"] = surfaces
        reference.setdefault("metadata", {})["visualReferenceMetrics"] = metrics
        if track_geometry_cleanup_enabled():
            reference = apply_kn5_geometry_cleanup(
                reference,
                target_spacing=target_spacing,
                smoothing_window=smoothing_window,
            )
        return reference
    except Exception as exc:
        logger.warning("ROAD-only visual reference failed; using physical centerline smoothing: %s", exc)
        return None


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
        cleanup_enabled = track_geometry_cleanup_enabled()
        visual_enabled = track_visual_geometry_enabled()
        visual_cfg = track_visual_geometry_config()
        cleanup_cfg = track_geometry_cleanup_config()
        target_spacing = float(cleanup_cfg["targetSpacingMeters"])
        smoothing_window = int(cleanup_cfg["smoothingWindow"])
        cache_name = kn5_surface_cache_name(track_name, track_config, cleaned=cleanup_enabled)
        cache_path = self.cache.cache_dir / f"{self.cache._safe_name(cache_name)}.json"
        cached = self.cache.load_track(cache_name)
        if cached and cached.get("provider") == self.provider:
            cached["cachePath"] = str(cache_path)
            cached["geometrySource"] = cached.get("geometrySource", self.source)
            cached.setdefault("metadata", {})["cachePath"] = str(cache_path)
            cached.setdefault("metadata", {})["cleanupEnabled"] = cleanup_enabled
            if visual_enabled and (
                not cached.get("visualGeometry")
                or cached.get("visualGeometry", {}).get("version") != VISUAL_GEOMETRY_VERSION
            ):
                visual_reference = None
                if visual_cfg.get("useRoadOnly", False):
                    try:
                        resolver = TrackFileResolver(ac_root=self.ac_root)
                        manifest = resolver.build_track_file_manifest(
                            track_name,
                            track_config,
                            source=source,
                            game_code=game_code,
                        )
                        visual_reference = build_visual_reference_track_from_manifest(
                            manifest.to_dict(),
                            visual_config=visual_cfg,
                            target_spacing=target_spacing,
                            smoothing_window=smoothing_window,
                        )
                    except Exception as exc:
                        logger.warning("Visual ROAD-only reference unavailable for cached geometry: %s", exc)
                cached = apply_track_visual_geometry(cached, config=visual_cfg, visual_reference_track=visual_reference)
                self.cache.save_track(cache_name, cached)
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

        raw_track_data = track_data_from_interval_edges(result, cache_path=cache_path)
        if cleanup_enabled:
            raw_track_data["cachePath"] = str(cache_path)
            track_data = apply_kn5_geometry_cleanup(
                raw_track_data,
                target_spacing=target_spacing,
                smoothing_window=smoothing_window,
            )
        else:
            track_data = raw_track_data
            track_data.setdefault("metadata", {})["targetSpacing"] = target_spacing
            track_data.setdefault("metadata", {})["smoothingWindow"] = smoothing_window
        if visual_enabled:
            visual_reference = None
            if visual_cfg.get("useRoadOnly", False):
                visual_reference = build_visual_reference_track_from_manifest(
                    manifest_dict,
                    visual_config=visual_cfg,
                    target_spacing=target_spacing,
                    smoothing_window=smoothing_window,
                )
            track_data = apply_track_visual_geometry(track_data, config=visual_cfg, visual_reference_track=visual_reference)
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
        cached["geometrySource"] = cached.get("geometrySource", cached["providerSource"])
        cached["cachePath"] = str(path)
        cached.setdefault("metadata", {})["cachePath"] = str(path)
        return TrackGeometryProviderResult(cache_name, cached, path, cached["provider"], cached["providerSource"], from_cache=True)


class DebugTrajectoryTrackGeometryProvider:
    provider = "debug_trajectory"
    source = "driver_trajectory_debug"

    @staticmethod
    def enabled() -> bool:
        return os.getenv("DEBUG_ALLOW_TRAJECTORY_TRACK", "false").strip().lower() in {"1", "true", "yes", "on"}
