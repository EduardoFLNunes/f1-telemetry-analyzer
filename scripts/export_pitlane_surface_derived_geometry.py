from __future__ import annotations

import json
import math
import struct
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.kn5.track_edges_from_surface import (  # noqa: E402
    _boundary_edges,
    _build_boundary_loops,
    _component_analysis,
)
from core.kn5.track_surface_polygon import build_track_surface_polygon_from_manifest  # noqa: E402
from core.track_file_resolver import TrackFileResolver  # noqa: E402


PIT_MESH_NAMES = {"1pitlane001", "1pitlane002", "1pitlane003"}
SLICE_SPACING_METERS = 2.0
MAX_REASONABLE_PIT_WIDTH = 35.0
MINIMAL_TRIM_CANDIDATES = [(0, 0), (5, 5), (8, 8), (10, 10), (12, 12)]
MINIMAL_TRIM_START_OPTIONS = [0, 3, 5, 8, 10, 12]
MINIMAL_TRIM_END_OPTIONS = [0, 3, 5, 8, 10, 12]


Point = Tuple[float, float]


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _round_point(point: Sequence[float], digits: int = 6) -> List[float]:
    return [_round(point[0], digits), _round(point[1], digits)]


def _xml(value: Any) -> str:
    return escape(str(value), quote=False)


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))


def _bounds(points: Iterable[Sequence[float]]) -> Optional[Dict[str, float]]:
    values = [(float(point[0]), float(point[1])) for point in points]
    if not values:
        return None
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    return {
        "minX": _round(min(xs)),
        "maxX": _round(max(xs)),
        "minY": _round(min(ys)),
        "maxY": _round(max(ys)),
        "width": _round(max(xs) - min(xs)),
        "height": _round(max(ys) - min(ys)),
    }


def _stats(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"min": None, "avg": None, "p95": None, "max": None}
    sorted_values = sorted(float(value) for value in values)
    p95_index = min(len(sorted_values) - 1, max(0, math.ceil(len(sorted_values) * 0.95) - 1))
    return {
        "min": _round(sorted_values[0]),
        "avg": _round(sum(sorted_values) / len(sorted_values)),
        "p95": _round(sorted_values[p95_index]),
        "max": _round(sorted_values[-1]),
    }


def _bbox_overlap(a: Optional[Dict[str, float]], b: Optional[Dict[str, float]]) -> Dict[str, float]:
    if not a or not b:
        return {"area": 0.0, "ratioA": 0.0, "ratioB": 0.0}
    width = max(0.0, min(a["maxX"], b["maxX"]) - max(a["minX"], b["minX"]))
    height = max(0.0, min(a["maxY"], b["maxY"]) - max(a["minY"], b["minY"]))
    area = width * height
    area_a = max(1e-9, float(a["width"]) * float(a["height"]))
    area_b = max(1e-9, float(b["width"]) * float(b["height"]))
    return {"area": _round(area), "ratioA": _round(area / area_a), "ratioB": _round(area / area_b)}


def _surface_bounds(triangles: Sequence[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    points: List[Sequence[float]] = []
    for triangle in triangles:
        points.extend(triangle.get("vertices", []))
    return _bounds(points)


def _load_main_track_geometry(track_name: str, track_config: str) -> Dict[str, Any]:
    cache_path = REPO_ROOT / "data" / "cache" / "tracks" / f"{track_name}_{track_config}_kn5_surface_interval_cleaned_geometry.json"
    if not cache_path.exists():
        return {"available": False, "path": str(cache_path), "centerline": [], "boundsLeft": [], "boundsRight": [], "bounds": None, "p": []}
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "path": str(cache_path),
        "provider": data.get("provider"),
        "geometrySource": data.get("geometrySource"),
        "trackLength": data.get("trackLength"),
        "centerline": data.get("centerline", []),
        "boundsLeft": data.get("boundsLeft", []),
        "boundsRight": data.get("boundsRight", []),
        "bounds": data.get("bounds"),
        "p": data.get("p", []),
        "pointCount": len(data.get("centerline", [])),
    }


def _track_point(point: Dict[str, Any]) -> Point:
    return float(point["x"]), float(point.get("y", point.get("z", 0.0)))


def _parse_ai_block20(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {"path": None, "pointCount": 0, "points": [], "diagnostics": [{"code": "missing_ai_path"}]}
    ai_path = Path(path)
    data = ai_path.read_bytes()
    if len(data) < 16:
        return {"path": str(ai_path), "pointCount": 0, "points": [], "diagnostics": [{"code": "invalid_ai_file"}]}
    version, point_count = struct.unpack_from("<II", data, 0)
    points = []
    offset = 16
    stride = 20
    available = max(0, (len(data) - offset) // stride)
    count = min(int(point_count), available)
    for index in range(count):
        point_offset = offset + index * stride
        x, y, z, distance, raw_index = struct.unpack_from("<3f f I", data, point_offset)
        points.append(
            {
                "index": index,
                "worldPosition": [_round(x), _round(y), _round(z)],
                "mapPosition": [_round(x), _round(-z)],
                "distance": _round(distance),
                "rawIndex": int(raw_index),
            }
        )
    diagnostics = []
    if count != point_count:
        diagnostics.append({"code": "ai_count_truncated", "declared": int(point_count), "available": available})
    return {"path": str(ai_path), "version": int(version), "declaredPointCount": int(point_count), "pointCount": len(points), "points": points, "diagnostics": diagnostics}


def _pca_axes(points: Sequence[Sequence[float]]) -> Dict[str, Any]:
    coords = np.array([[float(point[0]), float(point[1])] for point in points], dtype=float)
    mean = coords.mean(axis=0)
    centered = coords - mean
    cov = np.cov(centered.T)
    values, vectors = np.linalg.eigh(cov)
    order = np.argsort(values)[::-1]
    principal = vectors[:, order[0]]
    if principal[1] < 0:
        principal = -principal
    lateral = np.array([-principal[1], principal[0]])
    projected_u = centered @ principal
    projected_v = centered @ lateral
    return {
        "origin": [float(mean[0]), float(mean[1])],
        "longitudinalAxis": [float(principal[0]), float(principal[1])],
        "lateralAxis": [float(lateral[0]), float(lateral[1])],
        "uMin": float(projected_u.min()),
        "uMax": float(projected_u.max()),
        "vMin": float(projected_v.min()),
        "vMax": float(projected_v.max()),
    }


def _to_uv(point: Sequence[float], axes: Dict[str, Any]) -> Point:
    ox, oy = axes["origin"]
    ux, uy = axes["longitudinalAxis"]
    vx, vy = axes["lateralAxis"]
    dx = float(point[0]) - ox
    dy = float(point[1]) - oy
    return dx * ux + dy * uy, dx * vx + dy * vy


def _from_uv(u: float, v: float, axes: Dict[str, Any]) -> Point:
    ox, oy = axes["origin"]
    ux, uy = axes["longitudinalAxis"]
    vx, vy = axes["lateralAxis"]
    return ox + ux * u + vx * v, oy + uy * u + vy * v


def _intersections_at_u(boundary_edges: Sequence[Dict[str, Any]], axes: Dict[str, Any], u_value: float) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    for edge in boundary_edges:
        a = _to_uv(edge["from"], axes)
        b = _to_uv(edge["to"], axes)
        au, av = a
        bu, bv = b
        if abs(bu - au) <= 1e-9:
            continue
        if (u_value < min(au, bu) - 1e-7) or (u_value > max(au, bu) + 1e-7):
            continue
        t = (u_value - au) / (bu - au)
        if t < -1e-7 or t > 1.0000001:
            continue
        v = av + (bv - av) * t
        point = _from_uv(u_value, v, axes)
        hits.append({"v": float(v), "point": _round_point(point), "edgeId": edge.get("edgeId")})
    hits.sort(key=lambda hit: hit["v"])

    deduped: List[Dict[str, Any]] = []
    for hit in hits:
        if not deduped or abs(hit["v"] - deduped[-1]["v"]) > 0.03:
            deduped.append(hit)
    return deduped


def derive_pitlane_from_surface(boundary_edges: Sequence[Dict[str, Any]], surface_triangles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    vertices = [point for triangle in surface_triangles for point in triangle["vertices"]]
    axes = _pca_axes(vertices)
    u_min = axes["uMin"]
    u_max = axes["uMax"]
    spacing = SLICE_SPACING_METERS
    sample_count = max(2, int(math.floor((u_max - u_min) / spacing)) + 1)

    samples: List[Dict[str, Any]] = []
    for sample_index in range(sample_count + 1):
        u_value = u_min + (u_max - u_min) * sample_index / sample_count
        hits = _intersections_at_u(boundary_edges, axes, u_value)
        intervals = []
        for hit_index in range(0, len(hits) - 1, 2):
            low = hits[hit_index]
            high = hits[hit_index + 1]
            width = high["v"] - low["v"]
            if width <= 0:
                continue
            intervals.append({"low": low, "high": high, "width": width})
        if not intervals:
            continue
        plausible = [interval for interval in intervals if interval["width"] <= MAX_REASONABLE_PIT_WIDTH]
        selected = max(plausible or intervals, key=lambda interval: interval["width"])
        left_v = selected["low"]["v"]
        right_v = selected["high"]["v"]
        center_v = (left_v + right_v) * 0.5
        left = _from_uv(u_value, left_v, axes)
        right = _from_uv(u_value, right_v, axes)
        center = _from_uv(u_value, center_v, axes)
        samples.append(
            {
                "index": len(samples),
                "u": _round(u_value),
                "intersectionCount": len(hits),
                "intervalCount": len(intervals),
                "leftEdge": _round_point(left),
                "rightEdge": _round_point(right),
                "centerline": _round_point(center),
                "width": _round(selected["width"]),
            }
        )

    if len(samples) >= 2:
        # The PCA axis was oriented toward positive map Y. Keep this direction as
        # the physical pitlane candidate order for entry/exit reporting.
        cumulative = 0.0
        previous = samples[0]["centerline"]
        for sample in samples:
            center = sample["centerline"]
            if sample["index"] == 0:
                sample["distance"] = 0.0
            else:
                cumulative += _distance(previous, center)
                sample["distance"] = _round(cumulative)
            previous = center

    widths = [sample["width"] for sample in samples]
    return {
        "method": "surface_pca_cross_sections",
        "source": "PitLaneSurface 1pitlane001/1pitlane002/1pitlane003",
        "spacingMeters": spacing,
        "axes": {
            "origin": _round_point(axes["origin"]),
            "longitudinalAxis": _round_point(axes["longitudinalAxis"]),
            "lateralAxis": _round_point(axes["lateralAxis"]),
            "uMin": _round(axes["uMin"]),
            "uMax": _round(axes["uMax"]),
        },
        "samples": samples,
        "pitLeftEdge": [{"x": sample["leftEdge"][0], "y": sample["leftEdge"][1]} for sample in samples],
        "pitRightEdge": [{"x": sample["rightEdge"][0], "y": sample["rightEdge"][1]} for sample in samples],
        "pitCenterline": [{"x": sample["centerline"][0], "y": sample["centerline"][1], "distance": sample.get("distance", 0.0)} for sample in samples],
        "pitWidth": widths,
        "widthStats": _stats(widths),
        "diagnostics": [
            {
                "code": "debug_only_surface_derived",
                "message": "PitLaneGeometry is derived from 1pitlane* surface slices only; pit_lane.ai is not used for geometry.",
            }
        ],
    }


def _point_to_segment_distance(point: Sequence[float], start: Sequence[float], end: Sequence[float]) -> float:
    px, py = float(point[0]), float(point[1])
    ax, ay = float(start[0]), float(start[1])
    bx, by = float(end[0]), float(end[1])
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _nearest_polyline_distance(point: Sequence[float], polyline: Sequence[Sequence[float]]) -> float:
    if not polyline:
        return float("inf")
    if len(polyline) == 1:
        return _distance(point, polyline[0])
    return min(_point_to_segment_distance(point, polyline[index], polyline[index + 1]) for index in range(len(polyline) - 1))


def _nearest_main_track(point: Sequence[float], main_track: Dict[str, Any]) -> Dict[str, Any]:
    centerline = main_track.get("centerline") or []
    if not centerline:
        return {"index": None, "p": None, "distanceToMain": None, "point": None}
    target = [float(point[0]), float(point[1])]
    best_index = 0
    best_distance = float("inf")
    for index, track_point in enumerate(centerline):
        candidate = _track_point(track_point)
        distance = _distance(target, candidate)
        if distance < best_distance:
            best_distance = distance
            best_index = index
    p_values = main_track.get("p") or []
    nearest = _track_point(centerline[best_index])
    return {
        "index": best_index,
        "p": p_values[best_index] if best_index < len(p_values) else _round(best_index / max(1, len(centerline) - 1)),
        "distanceToMain": _round(best_distance),
        "point": {"x": _round(nearest[0]), "y": _round(nearest[1])},
    }


def _tangent(points: Sequence[Sequence[float]], index: int) -> Point:
    if len(points) < 2:
        return 1.0, 0.0
    prev_index = max(0, index - 1)
    next_index = min(len(points) - 1, index + 1)
    dx = float(points[next_index][0]) - float(points[prev_index][0])
    dy = float(points[next_index][1]) - float(points[prev_index][1])
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return 1.0, 0.0
    return dx / length, dy / length


def _angle_diff_deg(a: Sequence[float], b: Sequence[float]) -> float:
    dot = max(-1.0, min(1.0, float(a[0]) * float(b[0]) + float(a[1]) * float(b[1])))
    # Treat opposite direction as aligned for merge/divergence diagnostics.
    return _round(math.degrees(math.acos(abs(dot))))


def build_trim_profile(derived: Dict[str, Any], main_track: Dict[str, Any]) -> List[Dict[str, Any]]:
    pit_points = [[point["x"], point["y"]] for point in derived["pitCenterline"]]
    main_points = [_track_point(point) for point in main_track.get("centerline", [])]
    p_values = main_track.get("p") or []
    profile: List[Dict[str, Any]] = []
    for index, point in enumerate(pit_points):
        nearest_index = 0
        nearest_distance = float("inf")
        for main_index, main_point in enumerate(main_points):
            distance = _distance(point, main_point)
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_index = main_index
        main_tangent = _tangent(main_points, nearest_index) if main_points else (1.0, 0.0)
        pit_tangent = _tangent(pit_points, index)
        profile.append(
            {
                "pitIndex": index,
                "pitPosition": {"x": _round(point[0]), "y": _round(point[1])},
                "pitWidth": _round(derived["pitWidth"][index]),
                "distanceToMainCenterline": _round(nearest_distance),
                "nearestMainIndex": nearest_index if main_points else None,
                "nearestMainP": p_values[nearest_index] if nearest_index < len(p_values) else (_round(nearest_index / max(1, len(main_points) - 1)) if main_points else None),
                "tangentAngleDiffDeg": _angle_diff_deg(pit_tangent, main_tangent),
            }
        )
    return profile


def _first_sustained_width_drop(widths: Sequence[float], threshold: float, *, window: int = 5) -> Optional[int]:
    if len(widths) < window:
        return None
    for index in range(len(widths) - window + 1):
        if all(float(width) <= threshold for width in widths[index : index + window]):
            return index
    return None


def _first_after_index_with_distance(profile: Sequence[Dict[str, Any]], start_index: int, threshold: float) -> Optional[int]:
    for row in profile[start_index:]:
        if float(row["distanceToMainCenterline"]) >= threshold:
            return int(row["pitIndex"])
    return None


def _first_index_where(profile: Sequence[Dict[str, Any]], start: int, end: int, predicate) -> Optional[int]:
    for index in range(max(0, start), min(len(profile), end)):
        if predicate(profile[index]):
            return index
    return None


def choose_trim_indices(profile: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not profile:
        return {
            "selectedStartIndex": 0,
            "selectedEndIndex": -1,
            "candidateStartIndices": {},
            "candidateEndIndices": {},
            "startTrimReason": "missing_profile",
            "endTrimReason": "missing_profile",
        }
    widths = [float(row["pitWidth"]) for row in profile]
    width_median = sorted(widths)[len(widths) // 2]
    distance_threshold = 8.0
    width_drop_threshold = max(7.5, width_median * 0.65)

    search_head_end = max(8, int(len(profile) * 0.28))
    head_min_index = min(
        range(search_head_end),
        key=lambda index: float(profile[index]["distanceToMainCenterline"]),
    )
    start_by_distance = _first_after_index_with_distance(profile, head_min_index, distance_threshold)
    start_by_tangent = _first_index_where(
        profile,
        head_min_index,
        int(len(profile) * 0.45),
        lambda row: float(row["distanceToMainCenterline"]) >= distance_threshold and float(row["tangentAngleDiffDeg"]) <= 62.0,
    )
    start_by_width_stability = _first_index_where(
        profile,
        head_min_index,
        int(len(profile) * 0.45),
        lambda row: float(row["pitWidth"]) >= width_median * 0.92 and float(row["distanceToMainCenterline"]) >= distance_threshold,
    )
    start_by_surface_margin = max(0, int(round(len(profile) * 0.035)))

    width_drop_index = _first_sustained_width_drop(widths, width_drop_threshold, window=5)
    end_by_width = (width_drop_index - 1) if width_drop_index is not None else None
    tail_start = int(len(profile) * 0.58)
    end_merge_index = _first_index_where(
        profile,
        tail_start,
        len(profile),
        lambda row: float(row["distanceToMainCenterline"]) <= distance_threshold and float(row["pitWidth"]) <= width_median * 0.8,
    )
    end_by_distance = (end_merge_index - 1) if end_merge_index is not None else None
    end_by_tangent = _first_index_where(
        profile,
        tail_start,
        len(profile),
        lambda row: float(row["tangentAngleDiffDeg"]) <= 25.0 and float(row["pitWidth"]) <= width_median * 0.8,
    )
    end_by_tangent = (end_by_tangent - 1) if end_by_tangent is not None else None
    end_by_surface_margin = max(0, len(profile) - 1 - int(round(len(profile) * 0.035)))

    candidate_starts = {
        "byDistanceToMain": start_by_distance,
        "byWidthStability": start_by_width_stability,
        "byTangentDivergence": start_by_tangent,
        "bySurfaceEndpointMargin": start_by_surface_margin,
    }
    candidate_ends = {
        "byDistanceToMain": end_by_distance,
        "byWidthStability": end_by_width,
        "byTangentDivergence": end_by_tangent,
        "bySurfaceEndpointMargin": end_by_surface_margin,
    }

    selected_start = next(
        value
        for value in (start_by_width_stability, start_by_tangent, start_by_distance, start_by_surface_margin, 0)
        if value is not None
    )
    selected_end = next(
        value
        for value in (end_by_width, end_by_tangent, end_by_distance, end_by_surface_margin, len(profile) - 1)
        if value is not None
    )
    selected_start = max(0, min(int(selected_start), len(profile) - 2))
    selected_end = max(selected_start + 1, min(int(selected_end), len(profile) - 1))

    return {
        "selectedStartIndex": selected_start,
        "selectedEndIndex": selected_end,
        "candidateStartIndices": candidate_starts,
        "candidateEndIndices": candidate_ends,
        "startTrimReason": (
            "selected first stable/separate segment after the initial main-track merge valley; "
            f"distance threshold {distance_threshold}m"
        ),
        "endTrimReason": (
            "selected point before sustained width drop / final merge extension; "
            f"width drop threshold {round(width_drop_threshold, 3)}m"
        ),
        "diagnostics": {
            "widthMedian": _round(width_median),
            "distanceThreshold": distance_threshold,
            "widthDropThreshold": _round(width_drop_threshold),
            "initialMergeMinIndex": head_min_index,
            "initialMergeMinDistance": profile[head_min_index]["distanceToMainCenterline"],
        },
    }


def _polyline_length(points: Sequence[Sequence[float]]) -> float:
    if len(points) < 2:
        return 0.0
    return sum(_distance(points[index], points[index + 1]) for index in range(len(points) - 1))


def trim_derived_geometry(derived: Dict[str, Any], trim: Dict[str, Any]) -> Dict[str, Any]:
    start = int(trim["selectedStartIndex"])
    end = int(trim["selectedEndIndex"])
    samples = derived["samples"][start : end + 1]
    trimmed_samples = []
    cumulative = 0.0
    previous: Optional[List[float]] = None
    for new_index, sample in enumerate(samples):
        center = sample["centerline"]
        if previous is not None:
            cumulative += _distance(previous, center)
        copied = dict(sample)
        copied["rawIndex"] = sample["index"]
        copied["index"] = new_index
        copied["distance"] = _round(cumulative)
        trimmed_samples.append(copied)
        previous = center

    return {
        "method": "surface_pca_cross_sections_trimmed",
        "source": derived["source"],
        "rawSourceMethod": derived["method"],
        "trim": trim,
        "samples": trimmed_samples,
        "pitLeftEdge": [{"x": sample["leftEdge"][0], "y": sample["leftEdge"][1]} for sample in trimmed_samples],
        "pitRightEdge": [{"x": sample["rightEdge"][0], "y": sample["rightEdge"][1]} for sample in trimmed_samples],
        "pitCenterline": [{"x": sample["centerline"][0], "y": sample["centerline"][1], "distance": sample["distance"], "rawIndex": sample["rawIndex"]} for sample in trimmed_samples],
        "pitWidth": [sample["width"] for sample in trimmed_samples],
        "widthStats": _stats([sample["width"] for sample in trimmed_samples]),
        "diagnostics": [
            {
                "code": "debug_only_trimmed_pitlane",
                "message": "Trimmed pitlane geometry is debug/export only and is not connected to runtime.",
            }
        ],
    }


def _candidate_length(points: Sequence[Sequence[float]]) -> float:
    return _polyline_length(points)


def _subline_length(points: Sequence[Sequence[float]], start: int, end: int) -> float:
    if end <= start or not points:
        return 0.0
    end = min(end, len(points) - 1)
    start = max(0, start)
    return _polyline_length(points[start : end + 1])


def build_minimal_trim_candidates(derived: Dict[str, Any]) -> Dict[str, Any]:
    raw_center = [[point["x"], point["y"]] for point in derived["pitCenterline"]]
    raw_left = [[point["x"], point["y"]] for point in derived["pitLeftEdge"]]
    raw_right = [[point["x"], point["y"]] for point in derived["pitRightEdge"]]
    raw_width = list(derived["pitWidth"])
    raw_length = _candidate_length(raw_center)
    candidates: List[Dict[str, Any]] = []

    for start_trim, end_trim in MINIMAL_TRIM_CANDIDATES:
        start_index = min(start_trim, max(0, len(raw_center) - 1))
        end_index = max(start_index, len(raw_center) - 1 - end_trim)
        center = raw_center[start_index : end_index + 1]
        left = raw_left[start_index : end_index + 1]
        right = raw_right[start_index : end_index + 1]
        widths = raw_width[start_index : end_index + 1]
        name = f"candidate_{start_trim:02d}_{end_trim:02d}"
        candidates.append(
            {
                "name": name,
                "startTrimPoints": start_trim,
                "endTrimPoints": end_trim,
                "rawStartIndex": start_index,
                "rawEndIndex": end_index,
                "pointCount": len(center),
                "length": _round(_candidate_length(center)),
                "rawLength": _round(raw_length),
                "lengthRatioVsRaw": _round(_candidate_length(center) / raw_length if raw_length > 1e-9 else 0.0),
                "removedStartMeters": _round(_subline_length(raw_center, 0, start_index)),
                "removedEndMeters": _round(_subline_length(raw_center, end_index, len(raw_center) - 1)),
                "startCoordinate": {"x": _round(center[0][0]), "y": _round(center[0][1])} if center else None,
                "endCoordinate": {"x": _round(center[-1][0]), "y": _round(center[-1][1])} if center else None,
                "widthStats": _stats(widths),
                "pitLeftEdge": [{"x": point[0], "y": point[1]} for point in left],
                "pitRightEdge": [{"x": point[0], "y": point[1]} for point in right],
                "pitCenterline": [{"x": point[0], "y": point[1]} for point in center],
            }
        )

    return {
        "mode": "manual_parametric_minimal_trim",
        "autoSelection": False,
        "startOptions": MINIMAL_TRIM_START_OPTIONS,
        "endOptions": MINIMAL_TRIM_END_OPTIONS,
        "renderedCandidates": [candidate["name"] for candidate in candidates],
        "rawPointCount": len(raw_center),
        "rawLength": _round(raw_length),
        "candidates": candidates,
        "diagnostics": [
            {
                "code": "manual_decision_required",
                "message": "These candidates intentionally remove only a few raw points. No candidate is selected automatically.",
            }
        ],
    }


def map_to_svg(point: Sequence[float], bounds: Dict[str, float], padding: float, scale: float) -> Point:
    """Convert canonical map-space to SVG screen-space exactly once.

    All debug SVG layers use canonical map-space coordinates where mapX is X and
    mapY is already the projected -worldZ value. SVG Y grows downward, so this
    is the only place that flips Y for display.
    """

    screen_x = padding + (float(point[0]) - float(bounds["minX"])) * scale
    screen_y = padding + (float(bounds["maxY"]) - float(point[1])) * scale
    return screen_x, screen_y


def _svg_canvas(bounds: Dict[str, float], *, width: int = 1400, height: int = 1000, padding: int = 36) -> Dict[str, Any]:
    min_x, max_x = float(bounds["minX"]), float(bounds["maxX"])
    min_y, max_y = float(bounds["minY"]), float(bounds["maxY"])
    scale = min((width - padding * 2) / max(1.0, max_x - min_x), (height - padding * 2) / max(1.0, max_y - min_y))

    def sx(point: Sequence[float]) -> Point:
        return map_to_svg(point, bounds, padding, scale)

    return {"width": width, "height": height, "padding": padding, "scale": scale, "bounds": bounds, "sx": sx}


def _merge_bounds(*bounds_items: Optional[Dict[str, float]]) -> Dict[str, float]:
    valid = [bounds for bounds in bounds_items if bounds]
    if not valid:
        return {"minX": -1.0, "maxX": 1.0, "minY": -1.0, "maxY": 1.0, "width": 2.0, "height": 2.0}
    min_x = min(float(bounds["minX"]) for bounds in valid)
    max_x = max(float(bounds["maxX"]) for bounds in valid)
    min_y = min(float(bounds["minY"]) for bounds in valid)
    max_y = max(float(bounds["maxY"]) for bounds in valid)
    return {"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y, "width": max_x - min_x, "height": max_y - min_y}


def _polyline(points: Sequence[Sequence[float]], sx, *, stroke: str, width: float, opacity: float = 1.0, dash: Optional[str] = None) -> str:
    if not points:
        return ""
    points_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in (sx(point) for point in points))
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{points_text}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-opacity="{opacity}" stroke-linejoin="round" stroke-linecap="round"{dash_attr}/>'


def _polygon(points: Sequence[Sequence[float]], sx, *, fill: str, opacity: float, stroke: str = "none", width: float = 1.0) -> str:
    if not points:
        return ""
    points_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in (sx(point) for point in points))
    return f'<polygon points="{points_text}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{width}"/>'


def _draw_main_track(parts: List[str], sx, main_track: Dict[str, Any]) -> None:
    left = [_track_point(point) for point in main_track.get("boundsLeft", [])]
    right = [_track_point(point) for point in main_track.get("boundsRight", [])]
    if left and right:
        parts.append(_polygon(left + list(reversed(right)), sx, fill="#64748b", opacity=0.13, stroke="#94a3b8", width=0.5))
    elif main_track.get("centerline"):
        parts.append(_polyline([_track_point(point) for point in main_track["centerline"]], sx, stroke="#94a3b8", width=1.2, opacity=0.55))


def _draw_pit_surface(parts: List[str], sx, triangles: Sequence[Dict[str, Any]]) -> None:
    for triangle in triangles:
        parts.append(_polygon(triangle["vertices"], sx, fill="#eab308", opacity=0.26))


def _draw_boundary(parts: List[str], sx, loops: Sequence[Dict[str, Any]]) -> None:
    for loop in loops:
        parts.append(_polyline(loop.get("points", []), sx, stroke="#facc15", width=3.0, opacity=0.95))


def _draw_derived(parts: List[str], sx, derived: Dict[str, Any]) -> None:
    left = [[point["x"], point["y"]] for point in derived["pitLeftEdge"]]
    right = [[point["x"], point["y"]] for point in derived["pitRightEdge"]]
    center = [[point["x"], point["y"]] for point in derived["pitCenterline"]]
    parts.append(_polyline(left, sx, stroke="#38bdf8", width=2.2, opacity=0.95))
    parts.append(_polyline(right, sx, stroke="#fb7185", width=2.2, opacity=0.95))
    parts.append(_polyline(center, sx, stroke="#ffffff", width=2.0, opacity=0.92, dash="8,5"))
    if center:
        for point, color, label in ((center[0], "#22c55e", "entry candidate"), (center[-1], "#f97316", "exit candidate")):
            x, y = sx(point)
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{color}"/>')
            parts.append(f'<text x="{x + 7:.2f}" y="{y - 7:.2f}" fill="{color}" font-size="10" font-family="monospace">{_xml(label)}</text>')


def _draw_trimmed(parts: List[str], sx, trimmed: Dict[str, Any]) -> None:
    left = [[point["x"], point["y"]] for point in trimmed["pitLeftEdge"]]
    right = [[point["x"], point["y"]] for point in trimmed["pitRightEdge"]]
    center = [[point["x"], point["y"]] for point in trimmed["pitCenterline"]]
    if left and right:
        parts.append(_polygon(left + list(reversed(right)), sx, fill="#facc15", opacity=0.34, stroke="#facc15", width=1.0))
    parts.append(_polyline(center, sx, stroke="#facc15", width=3.0, opacity=0.98))
    if center:
        for point, color, label in ((center[0], "#fb923c", "trimmed start"), (center[-1], "#38bdf8", "trimmed end")):
            x, y = sx(point)
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="{color}"/>')
            parts.append(f'<text x="{x + 8:.2f}" y="{y - 8:.2f}" fill="{color}" font-size="10" font-family="monospace">{_xml(label)}</text>')


def _draw_raw_endpoints(parts: List[str], sx, derived: Dict[str, Any]) -> None:
    center = [[point["x"], point["y"]] for point in derived["pitCenterline"]]
    if not center:
        return
    for point, color, label in ((center[0], "#fdba74", "raw start"), (center[-1], "#93c5fd", "raw end")):
        x, y = sx(point)
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}" fill-opacity="0.62"/>')
        parts.append(f'<text x="{x + 7:.2f}" y="{y + 13:.2f}" fill="{color}" fill-opacity="0.82" font-size="10" font-family="monospace">{_xml(label)}</text>')


def _draw_trim_candidates(parts: List[str], sx, derived: Dict[str, Any], trim: Dict[str, Any]) -> None:
    center = [[point["x"], point["y"]] for point in derived["pitCenterline"]]
    seen: set[int] = set()
    for group_name in ("candidateStartIndices", "candidateEndIndices"):
        for reason, raw_index in (trim.get(group_name) or {}).items():
            if raw_index is None:
                continue
            index = int(raw_index)
            if index < 0 or index >= len(center):
                continue
            point = center[index]
            x, y = sx(point)
            radius = 3.5 if index not in seen else 5.0
            seen.add(index)
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="#ffffff" fill-opacity="0.95"/>')
            parts.append(f'<text x="{x + 6:.2f}" y="{y + 5:.2f}" fill="#f8fafc" font-size="9" font-family="monospace">{_xml(reason)}:{index}</text>')


def _draw_minimal_trim_candidates(parts: List[str], sx, minimal: Dict[str, Any]) -> None:
    colors = ["#22c55e", "#38bdf8", "#a855f7", "#f97316", "#ef4444"]
    for index, candidate in enumerate(minimal.get("candidates", [])):
        color = colors[index % len(colors)]
        center = [[point["x"], point["y"]] for point in candidate["pitCenterline"]]
        parts.append(_polyline(center, sx, stroke=color, width=2.0 + index * 0.25, opacity=0.92, dash=None if index == 0 else "9,5"))
        if center:
            for point, label_suffix in ((center[0], "start"), (center[-1], "end")):
                x, y = sx(point)
                parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{3.5 + index * 0.3:.2f}" fill="{color}" fill-opacity="0.95"/>')
                parts.append(f'<text x="{x + 5:.2f}" y="{y + 5 + index * 8:.2f}" fill="{color}" font-size="8" font-family="monospace">{_xml(candidate["name"])} {label_suffix}</text>')


def _write_minimal_trim_zoom_svg(
    path: Path,
    *,
    main_track: Dict[str, Any],
    triangles: Sequence[Dict[str, Any]],
    loops: Sequence[Dict[str, Any]],
    derived: Dict[str, Any],
    minimal_trim: Dict[str, Any],
) -> None:
    width = 1400
    height = 780
    panel_w = 680
    panel_h = 690
    top = 64
    margin = 30
    colors = ["#22c55e", "#38bdf8", "#a855f7", "#f97316", "#ef4444"]
    raw_center = [[point["x"], point["y"]] for point in derived["pitCenterline"]]
    raw_left = [[point["x"], point["y"]] for point in derived["pitLeftEdge"]]
    raw_right = [[point["x"], point["y"]] for point in derived["pitRightEdge"]]

    def local_bounds(points: Sequence[Sequence[float]], pad: float = 32.0) -> Dict[str, float]:
        bounds = _bounds(points) or {"minX": -1.0, "maxX": 1.0, "minY": -1.0, "maxY": 1.0, "width": 2.0, "height": 2.0}
        return {
            "minX": bounds["minX"] - pad,
            "maxX": bounds["maxX"] + pad,
            "minY": bounds["minY"] - pad,
            "maxY": bounds["maxY"] + pad,
            "width": bounds["width"] + pad * 2,
            "height": bounds["height"] + pad * 2,
        }

    start_points: List[Sequence[float]] = raw_center[:26] + raw_left[:26] + raw_right[:26]
    end_points: List[Sequence[float]] = raw_center[-26:] + raw_left[-26:] + raw_right[-26:]
    for candidate in minimal_trim.get("candidates", []):
        center = [[point["x"], point["y"]] for point in candidate["pitCenterline"]]
        if center:
            start_points.append(center[0])
            end_points.append(center[-1])
    start_bounds = local_bounds(start_points)
    end_bounds = local_bounds(end_points)

    def panel_mapper(bounds: Dict[str, float], ox: float):
        scale = min((panel_w - margin * 2) / max(1.0, bounds["maxX"] - bounds["minX"]), (panel_h - margin * 2) / max(1.0, bounds["maxY"] - bounds["minY"]))

        def sx(point: Sequence[float]) -> Point:
            x, y = map_to_svg(point, bounds, margin, scale)
            return x + ox, y + top

        return sx

    start_sx = panel_mapper(start_bounds, 0)
    end_sx = panel_mapper(end_bounds, panel_w + 20)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#080b10"/>',
        '<text x="18" y="28" fill="#e2e8f0" font-size="15" font-family="monospace">PitLane minimal trim zoom: start/end comparison</text>',
        '<text x="18" y="48" fill="#94a3b8" font-size="11" font-family="monospace">manual visual decision only; no runtime changes; no candidate selected automatically</text>',
        f'<rect x="0" y="{top}" width="{panel_w}" height="{panel_h}" fill="#0b1020" stroke="#1e293b"/>',
        f'<rect x="{panel_w + 20}" y="{top}" width="{panel_w}" height="{panel_h}" fill="#0b1020" stroke="#1e293b"/>',
        f'<text x="18" y="{top + 24}" fill="#e2e8f0" font-size="13" font-family="monospace">START ZOOM</text>',
        f'<text x="{panel_w + 38}" y="{top + 24}" fill="#e2e8f0" font-size="13" font-family="monospace">END ZOOM</text>',
    ]

    def draw_panel(sx, is_start: bool) -> None:
        left = [_track_point(point) for point in main_track.get("boundsLeft", [])]
        right = [_track_point(point) for point in main_track.get("boundsRight", [])]
        if left and right:
            parts.append(_polygon(left + list(reversed(right)), sx, fill="#64748b", opacity=0.12, stroke="#94a3b8", width=0.5))
        for triangle in triangles:
            parts.append(_polygon(triangle["vertices"], sx, fill="#eab308", opacity=0.18))
        for loop in loops:
            parts.append(_polyline(loop.get("points", []), sx, stroke="#facc15", width=1.4, opacity=0.42))
        parts.append(_polyline(raw_center, sx, stroke="#facc15", width=3.0, opacity=0.38))
        raw_point = raw_center[0] if is_start else raw_center[-1]
        rx, ry = sx(raw_point)
        raw_label = "rawStart" if is_start else "rawEnd"
        parts.append(f'<circle cx="{rx:.2f}" cy="{ry:.2f}" r="6" fill="#facc15" fill-opacity="0.72"/>')
        parts.append(f'<text x="{rx + 8:.2f}" y="{ry - 8:.2f}" fill="#facc15" font-size="10" font-family="monospace">{raw_label}</text>')
        for index, candidate in enumerate(minimal_trim.get("candidates", [])):
            color = colors[index % len(colors)]
            center = [[point["x"], point["y"]] for point in candidate["pitCenterline"]]
            if not center:
                continue
            parts.append(_polyline(center, sx, stroke=color, width=2.2, opacity=0.92, dash=None if index == 0 else "8,4"))
            marker = center[0] if is_start else center[-1]
            mx, my = sx(marker)
            removed = candidate["removedStartMeters"] if is_start else candidate["removedEndMeters"]
            parts.append(f'<circle cx="{mx:.2f}" cy="{my:.2f}" r="{4 + index * 0.25:.2f}" fill="{color}"/>')
            label_y = my + 11 + index * 12
            parts.append(
                f'<text x="{mx + 8:.2f}" y="{label_y:.2f}" fill="{color}" font-size="10" font-family="monospace">'
                f'{_xml(candidate["name"])} removes {removed:.2f}m</text>'
            )

    draw_panel(start_sx, True)
    draw_panel(end_sx, False)

    legend_x = 18
    legend_y = height - 92
    parts.append(f'<text x="{legend_x}" y="{legend_y}" fill="#cbd5e1" font-size="11" font-family="monospace">colors:</text>')
    for index, candidate in enumerate(minimal_trim.get("candidates", [])):
        color = colors[index % len(colors)]
        y = legend_y + 18 + index * 14
        parts.append(f'<rect x="{legend_x}" y="{y - 9}" width="9" height="9" fill="{color}"/>')
        parts.append(f'<text x="{legend_x + 14}" y="{y}" fill="{color}" font-size="10" font-family="monospace">{_xml(candidate["name"])}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(part for part in parts if part), encoding="utf-8")


def _draw_legend(parts: List[str], items: Sequence[Tuple[str, str]], x: int = 18, y: int = 92) -> None:
    for index, (label, color) in enumerate(items):
        yy = y + index * 18
        parts.append(f'<rect x="{x}" y="{yy - 10}" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="{x + 16}" y="{yy}" fill="#cbd5e1" font-size="11" font-family="monospace">{_xml(label)}</text>')


def _draw_map_axes(parts: List[str], canvas: Dict[str, Any]) -> None:
    padding = float(canvas["padding"])
    scale = float(canvas["scale"])
    bounds = canvas["bounds"]
    origin = [float(bounds["minX"]) + 18.0 / scale, float(bounds["maxY"]) - 58.0 / scale]
    x_tip = [origin[0] + 28.0 / scale, origin[1]]
    y_tip = [origin[0], origin[1] + 28.0 / scale]
    sx = canvas["sx"]
    ox, oy = sx(origin)
    xx, xy = sx(x_tip)
    yx, yy = sx(y_tip)
    parts.append(f'<line x1="{ox:.2f}" y1="{oy:.2f}" x2="{xx:.2f}" y2="{xy:.2f}" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrow)"/>')
    parts.append(f'<line x1="{ox:.2f}" y1="{oy:.2f}" x2="{yx:.2f}" y2="{yy:.2f}" stroke="#22c55e" stroke-width="2" marker-end="url(#arrow)"/>')
    parts.append(f'<text x="{xx + 4:.2f}" y="{xy + 4:.2f}" fill="#38bdf8" font-size="10" font-family="monospace">+X</text>')
    parts.append(f'<text x="{yx + 4:.2f}" y="{yy + 4:.2f}" fill="#22c55e" font-size="10" font-family="monospace">+Y</text>')
    min_point = [bounds["minX"], bounds["minY"]]
    max_point = [bounds["maxX"], bounds["maxY"]]
    min_x, min_y = sx(min_point)
    max_x, max_y = sx(max_point)
    parts.append(f'<circle cx="{min_x:.2f}" cy="{min_y:.2f}" r="3" fill="#f97316"/>')
    parts.append(f'<circle cx="{max_x:.2f}" cy="{max_y:.2f}" r="3" fill="#a78bfa"/>')
    parts.append(f'<text x="{min_x + 5:.2f}" y="{min_y - 5:.2f}" fill="#f97316" font-size="9" font-family="monospace">bounds min</text>')
    parts.append(f'<text x="{max_x + 5:.2f}" y="{max_y + 12:.2f}" fill="#a78bfa" font-size="9" font-family="monospace">bounds max</text>')


def _write_svg(
    path: Path,
    *,
    title: str,
    bounds: Dict[str, float],
    main_track: Dict[str, Any],
    triangles: Sequence[Dict[str, Any]],
    loops: Sequence[Dict[str, Any]],
    derived: Optional[Dict[str, Any]] = None,
    trimmed: Optional[Dict[str, Any]] = None,
    trim: Optional[Dict[str, Any]] = None,
    minimal_trim: Optional[Dict[str, Any]] = None,
    show_raw_endpoints: bool = False,
    show_candidates: bool = False,
    pit_ai: Optional[Dict[str, Any]] = None,
) -> None:
    canvas = _svg_canvas(bounds)
    sx = canvas["sx"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas["width"]}" height="{canvas["height"]}" viewBox="0 0 {canvas["width"]} {canvas["height"]}">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#080b10"/>',
        f'<text x="18" y="28" fill="#e2e8f0" font-size="15" font-family="monospace">{_xml(title)}</text>',
        '<text x="18" y="50" fill="#94a3b8" font-size="11" font-family="monospace">debug/export only; runtime and main geometry unchanged; mapX=x,mapY=-z</text>',
        '<text x="18" y="68" fill="#94a3b8" font-size="11" font-family="monospace">map-space projected consistently: screenX=padding+(mapX-minX)*scale, screenY=padding+(maxY-mapY)*scale</text>',
    ]
    _draw_main_track(parts, sx, main_track)
    _draw_pit_surface(parts, sx, triangles)
    _draw_boundary(parts, sx, loops)
    if derived:
        _draw_derived(parts, sx, derived)
    if show_raw_endpoints and derived:
        _draw_raw_endpoints(parts, sx, derived)
    if trimmed:
        _draw_trimmed(parts, sx, trimmed)
    if show_candidates and derived and trim:
        _draw_trim_candidates(parts, sx, derived, trim)
    if minimal_trim:
        _draw_minimal_trim_candidates(parts, sx, minimal_trim)
    if pit_ai:
        ai_points = [point["mapPosition"] for point in pit_ai.get("points", [])]
        parts.append(_polyline(ai_points, sx, stroke="#fde68a", width=1.4, opacity=0.75, dash="4,6"))
        if ai_points:
            x, y = sx(ai_points[0])
            parts.append(f'<text x="{x + 8:.2f}" y="{y - 8:.2f}" fill="#fde68a" font-size="10" font-family="monospace">AI route, not physical pit centerline</text>')
    legend = [
        ("MainTrackGeometry", "#94a3b8"),
        ("PitLaneSurface 1pitlane*", "#eab308"),
        ("boundary loops", "#facc15"),
    ]
    if derived:
        legend.extend([("derived left/right", "#38bdf8"), ("derived centerline", "#ffffff")])
    if trimmed:
        legend.append(("PitLane trimmed", "#facc15"))
    if show_candidates:
        legend.append(("trim candidates", "#ffffff"))
    if minimal_trim:
        legend.append(("minimal trim candidates", "#22c55e"))
    if pit_ai:
        legend.append(("pit_lane.ai overlay only", "#fde68a"))
    _draw_legend(parts, legend)
    _draw_map_axes(parts, canvas)
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    track_name = sys.argv[1] if len(sys.argv) > 1 else "vhe_interlagos"
    track_config = sys.argv[2] if len(sys.argv) > 2 else "gp"
    output_dir = REPO_ROOT / "data" / "debug"
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = TrackFileResolver().build_track_file_manifest(
        track_name,
        track_config,
        source="assetto_corsa",
        game_code="assetto_corsa",
    ).to_dict()
    surface = build_track_surface_polygon_from_manifest(manifest, included_surfaces=["PITLANE"])
    all_triangles = surface.get("triangles", [])
    pit_triangles = [
        triangle
        for triangle in all_triangles
        if str(triangle.get("mesh", "")).lower() in PIT_MESH_NAMES
    ]
    if not pit_triangles:
        raise RuntimeError("No 1pitlane001/002/003 triangles were extracted")

    components, triangle_to_component = _component_analysis(pit_triangles)
    selected_component_id = components[0]["componentId"] if components else 0
    selected_indices = [index for index, component_id in triangle_to_component.items() if component_id == selected_component_id]
    boundary_edges, node_points = _boundary_edges(pit_triangles, selected_indices)
    raw_loops, clean_loops = _build_boundary_loops(boundary_edges, node_points)
    derived = derive_pitlane_from_surface(boundary_edges, [pit_triangles[index] for index in selected_indices])

    main_track = _load_main_track_geometry(track_name, track_config)
    pit_ai = _parse_ai_block20((manifest.get("aiFiles") or {}).get("pit_lane"))
    trim_profile = build_trim_profile(derived, main_track)
    trim = choose_trim_indices(trim_profile)
    trimmed = trim_derived_geometry(derived, trim)
    minimal_trim = build_minimal_trim_candidates(derived)

    pit_centerline_points = [[point["x"], point["y"]] for point in derived["pitCenterline"]]
    trimmed_centerline_points = [[point["x"], point["y"]] for point in trimmed["pitCenterline"]]
    ai_distances = [
        _nearest_polyline_distance(point["mapPosition"], pit_centerline_points)
        for point in pit_ai.get("points", [])
    ]
    entry_point = pit_centerline_points[0] if pit_centerline_points else None
    exit_point = pit_centerline_points[-1] if pit_centerline_points else None
    entry_nearest = _nearest_main_track(entry_point, main_track) if entry_point else {}
    exit_nearest = _nearest_main_track(exit_point, main_track) if exit_point else {}
    trimmed_entry_point = trimmed_centerline_points[0] if trimmed_centerline_points else None
    trimmed_exit_point = trimmed_centerline_points[-1] if trimmed_centerline_points else None
    trimmed_entry_nearest = _nearest_main_track(trimmed_entry_point, main_track) if trimmed_entry_point else {}
    trimmed_exit_nearest = _nearest_main_track(trimmed_exit_point, main_track) if trimmed_exit_point else {}

    bounds = _merge_bounds(_surface_bounds(pit_triangles), main_track.get("bounds"), _bounds(pit_centerline_points), _bounds(trimmed_centerline_points))
    pit_surface_bounds = _surface_bounds(pit_triangles)
    boundary_payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "trackName": track_name,
        "trackConfig": track_config,
        "runtimeChanged": False,
        "source": "PitLaneSurface 1pitlane001/1pitlane002/1pitlane003",
        "projection": "mapX = worldX, mapY = -worldZ",
        "pitSurfaceTriangles": pit_triangles,
        "pitBoundaryEdges": boundary_edges,
        "pitBoundaryLoops": {"rawLoops": raw_loops, "cleanLoops": clean_loops},
        "pitSurfaceBounds": pit_surface_bounds,
        "components": components,
        "diagnostics": [
            {"code": "debug_only", "message": "This file is an offline pitlane surface boundary export only."}
        ],
    }

    geometry_payload = {
        "generatedAt": boundary_payload["generatedAt"],
        "trackName": track_name,
        "trackConfig": track_config,
        "runtimeChanged": False,
        "source": "PitLaneSurface 1pitlane001/1pitlane002/1pitlane003",
        "projection": "mapX = worldX, mapY = -worldZ",
        "pitSurfaceBounds": pit_surface_bounds,
        "pitLeftEdge": derived["pitLeftEdge"],
        "pitCenterline": derived["pitCenterline"],
        "pitRightEdge": derived["pitRightEdge"],
        "pitWidth": derived["pitWidth"],
        "metadata": {
            "method": derived["method"],
            "spacingMeters": derived["spacingMeters"],
            "axes": derived["axes"],
            "widthStats": derived["widthStats"],
            "pitLaneAiUsage": "overlay_diagnostic_only",
        },
        "samples": derived["samples"],
        "diagnostics": derived["diagnostics"],
    }

    trimmed_geometry_payload = {
        "generatedAt": boundary_payload["generatedAt"],
        "trackName": track_name,
        "trackConfig": track_config,
        "runtimeChanged": False,
        "source": "PitLaneSurface 1pitlane001/1pitlane002/1pitlane003",
        "projection": "mapX = worldX, mapY = -worldZ",
        "rawGeometrySource": "interlagos_pitlane_surface_derived_geometry.json",
        "trim": trim,
        "pitSurfaceBounds": pit_surface_bounds,
        "pitLeftEdge": trimmed["pitLeftEdge"],
        "pitCenterline": trimmed["pitCenterline"],
        "pitRightEdge": trimmed["pitRightEdge"],
        "pitWidth": trimmed["pitWidth"],
        "metadata": {
            "method": trimmed["method"],
            "widthStats": trimmed["widthStats"],
            "pitLaneAiUsage": "overlay_diagnostic_only",
        },
        "samples": trimmed["samples"],
        "diagnostics": trimmed["diagnostics"],
    }

    report = {
        "generatedAt": boundary_payload["generatedAt"],
        "trackName": track_name,
        "trackConfig": track_config,
        "runtimeChanged": False,
        "mainTrackGeometryChanged": False,
        "trackPhysicsGeometryChanged": False,
        "pitLaneAiUsedForGeometry": False,
        "pitSurfaceTriangleCount": len(pit_triangles),
        "pitBoundaryEdgeCount": len(boundary_edges),
        "pitBoundaryLoopCount": len(clean_loops),
        "pitCenterlinePointCount": len(derived["pitCenterline"]),
        "pitWidthMin": derived["widthStats"]["min"],
        "pitWidthAvg": derived["widthStats"]["avg"],
        "pitWidthMax": derived["widthStats"]["max"],
        "pitEntryCandidate": {
            "point": {"x": _round(entry_point[0]), "y": _round(entry_point[1])} if entry_point else None,
            "nearestMainTrack": entry_nearest,
        },
        "pitExitCandidate": {
            "point": {"x": _round(exit_point[0]), "y": _round(exit_point[1])} if exit_point else None,
            "nearestMainTrack": exit_nearest,
        },
        "distanceFromPitAiToDerivedCenterlineAvg": _stats(ai_distances)["avg"],
        "distanceFromPitAiToDerivedCenterlineP95": _stats(ai_distances)["p95"],
        "pitLaneAiOverlay": {
            "path": pit_ai.get("path"),
            "pointCount": pit_ai.get("pointCount"),
            "usage": "AI route, not physical pit centerline",
            "bboxOverlapWithPitSurface": _bbox_overlap(_bounds([point["mapPosition"] for point in pit_ai.get("points", [])]), pit_surface_bounds),
        },
        "diagnostics": [
            {
                "code": "pitlane_surface_derived_geometry_debug_only",
                "message": "PitLaneGeometry was derived from 1pitlane* surface cross-sections. Runtime is untouched.",
            },
            *derived["diagnostics"],
        ],
    }

    trim_report = {
        "generatedAt": boundary_payload["generatedAt"],
        "trackName": track_name,
        "trackConfig": track_config,
        "runtimeChanged": False,
        "pitLaneAiUsedForGeometry": False,
        "rawPointCount": len(derived["pitCenterline"]),
        "trimmedPointCount": len(trimmed["pitCenterline"]),
        "removedStartPoints": trim["selectedStartIndex"],
        "removedEndPoints": max(0, len(derived["pitCenterline"]) - 1 - trim["selectedEndIndex"]),
        "rawLength": _round(_polyline_length(pit_centerline_points)),
        "trimmedLength": _round(_polyline_length(trimmed_centerline_points)),
        "startTrimReason": trim["startTrimReason"],
        "endTrimReason": trim["endTrimReason"],
        "selectedStartIndex": trim["selectedStartIndex"],
        "selectedEndIndex": trim["selectedEndIndex"],
        "candidateStartIndices": trim["candidateStartIndices"],
        "candidateEndIndices": trim["candidateEndIndices"],
        "rawStart": {"x": _round(entry_point[0]), "y": _round(entry_point[1])} if entry_point else None,
        "rawEnd": {"x": _round(exit_point[0]), "y": _round(exit_point[1])} if exit_point else None,
        "trimmedStart": {"x": _round(trimmed_entry_point[0]), "y": _round(trimmed_entry_point[1])} if trimmed_entry_point else None,
        "trimmedEnd": {"x": _round(trimmed_exit_point[0]), "y": _round(trimmed_exit_point[1])} if trimmed_exit_point else None,
        "trimmedStartNearestMain": trimmed_entry_nearest,
        "trimmedEndNearestMain": trimmed_exit_nearest,
        "widthStatsRaw": derived["widthStats"],
        "widthStatsTrimmed": trimmed["widthStats"],
        "trimDiagnostics": trim.get("diagnostics", {}),
        "diagnostics": [
            {
                "code": "debug_only_trim",
                "message": "PitLaneGeometryTrimmed is exported for validation only; runtime and main track geometries are unchanged.",
            },
            *trimmed["diagnostics"],
        ],
    }

    boundary_json = output_dir / "interlagos_pitlane_surface_boundary.json"
    boundary_svg = output_dir / "interlagos_pitlane_surface_boundary.svg"
    geometry_json = output_dir / "interlagos_pitlane_surface_derived_geometry.json"
    geometry_svg = output_dir / "interlagos_pitlane_surface_derived_geometry.svg"
    vs_ai_svg = output_dir / "interlagos_pitlane_surface_vs_ai_route.svg"
    report_json = output_dir / "interlagos_pitlane_surface_centerline_report.json"
    trim_profile_json = output_dir / "interlagos_pitlane_trim_profile.json"
    trimmed_geometry_json = output_dir / "interlagos_pitlane_trimmed_geometry.json"
    raw_vs_trimmed_svg = output_dir / "interlagos_pitlane_raw_vs_trimmed.svg"
    trim_candidates_svg = output_dir / "interlagos_pitlane_trim_candidates.svg"
    trimmed_geometry_svg = output_dir / "interlagos_pitlane_trimmed_geometry.svg"
    trim_report_json = output_dir / "interlagos_pitlane_trim_report.json"
    minimal_trim_json = output_dir / "interlagos_pitlane_trim_candidates_minimal.json"
    minimal_trim_svg = output_dir / "interlagos_pitlane_trim_candidates_minimal.svg"
    minimal_trim_zoom_svg = output_dir / "interlagos_pitlane_minimal_trim_zoom_start_end.svg"

    boundary_json.write_text(json.dumps(boundary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    geometry_json.write_text(json.dumps(geometry_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    trim_profile_json.write_text(
        json.dumps(
            {
                "generatedAt": boundary_payload["generatedAt"],
                "trackName": track_name,
                "trackConfig": track_config,
                "runtimeChanged": False,
                "profile": trim_profile,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    trimmed_geometry_json.write_text(json.dumps(trimmed_geometry_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    trim_report_json.write_text(json.dumps(trim_report, ensure_ascii=False, indent=2), encoding="utf-8")
    minimal_trim_json.write_text(
        json.dumps(
            {
                "generatedAt": boundary_payload["generatedAt"],
                "trackName": track_name,
                "trackConfig": track_config,
                "runtimeChanged": False,
                "pitLaneGeometryRawChanged": False,
                "pitLaneAiUsedForGeometry": False,
                **minimal_trim,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    _write_svg(
        boundary_svg,
        title="PitLaneSurface boundary from 1pitlane001/002/003",
        bounds=bounds,
        main_track=main_track,
        triangles=pit_triangles,
        loops=clean_loops,
    )
    _write_svg(
        geometry_svg,
        title="PitLaneGeometry derived from PitLaneSurface cross-sections",
        bounds=bounds,
        main_track=main_track,
        triangles=pit_triangles,
        loops=clean_loops,
        derived=derived,
    )
    _write_svg(
        vs_ai_svg,
        title="PitLaneSurface-derived centerline vs pit_lane.ai diagnostic route",
        bounds=bounds,
        main_track=main_track,
        triangles=pit_triangles,
        loops=clean_loops,
        derived=derived,
        pit_ai=pit_ai,
    )
    _write_svg(
        raw_vs_trimmed_svg,
        title="PitLaneGeometry raw vs trimmed candidates",
        bounds=bounds,
        main_track=main_track,
        triangles=pit_triangles,
        loops=clean_loops,
        derived=derived,
        trimmed=trimmed,
        trim=trim,
        show_raw_endpoints=True,
    )
    _write_svg(
        trim_candidates_svg,
        title="PitLane trim candidates from width/distance/tangent profile",
        bounds=bounds,
        main_track=main_track,
        triangles=pit_triangles,
        loops=clean_loops,
        derived=derived,
        trimmed=trimmed,
        trim=trim,
        show_raw_endpoints=True,
        show_candidates=True,
    )
    _write_svg(
        trimmed_geometry_svg,
        title="PitLaneGeometryTrimmed from surface-derived corridor",
        bounds=bounds,
        main_track=main_track,
        triangles=pit_triangles,
        loops=clean_loops,
        trimmed=trimmed,
    )
    _write_svg(
        minimal_trim_svg,
        title="PitLane minimal manual trim candidates from raw surface-derived corridor",
        bounds=bounds,
        main_track=main_track,
        triangles=pit_triangles,
        loops=clean_loops,
        derived=derived,
        minimal_trim=minimal_trim,
        show_raw_endpoints=True,
    )
    _write_minimal_trim_zoom_svg(
        minimal_trim_zoom_svg,
        main_track=main_track,
        triangles=pit_triangles,
        loops=clean_loops,
        derived=derived,
        minimal_trim=minimal_trim,
    )

    print(
        json.dumps(
            {
                "pitSurfaceTriangleCount": report["pitSurfaceTriangleCount"],
                "pitBoundaryEdgeCount": report["pitBoundaryEdgeCount"],
                "pitBoundaryLoopCount": report["pitBoundaryLoopCount"],
                "pitCenterlinePointCount": report["pitCenterlinePointCount"],
                "pitWidthMin": report["pitWidthMin"],
                "pitWidthAvg": report["pitWidthAvg"],
                "pitWidthMax": report["pitWidthMax"],
                "distanceFromPitAiToDerivedCenterlineAvg": report["distanceFromPitAiToDerivedCenterlineAvg"],
                "distanceFromPitAiToDerivedCenterlineP95": report["distanceFromPitAiToDerivedCenterlineP95"],
                "selectedStartIndex": trim_report["selectedStartIndex"],
                "selectedEndIndex": trim_report["selectedEndIndex"],
                "trimmedPointCount": trim_report["trimmedPointCount"],
                "rawLength": trim_report["rawLength"],
                "trimmedLength": trim_report["trimmedLength"],
                "exports": {
                    "boundaryJson": str(boundary_json),
                    "boundarySvg": str(boundary_svg),
                    "derivedGeometryJson": str(geometry_json),
                    "derivedGeometrySvg": str(geometry_svg),
                    "surfaceVsAiSvg": str(vs_ai_svg),
                    "reportJson": str(report_json),
                    "trimProfileJson": str(trim_profile_json),
                    "trimmedGeometryJson": str(trimmed_geometry_json),
                    "rawVsTrimmedSvg": str(raw_vs_trimmed_svg),
                    "trimCandidatesSvg": str(trim_candidates_svg),
                    "trimmedGeometrySvg": str(trimmed_geometry_svg),
                    "trimReportJson": str(trim_report_json),
                    "minimalTrimJson": str(minimal_trim_json),
                    "minimalTrimSvg": str(minimal_trim_svg),
                    "minimalTrimZoomSvg": str(minimal_trim_zoom_svg),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
