"""Regenerate debug-only Interlagos PitLaneGeometry using transform B.

Transform B is mapX=worldX,mapY=worldZ. This script writes separate debug
artifacts only; it does not change runtime providers or authoritative geometry.
"""
from __future__ import annotations

import html
import json
import math
import struct
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.kn5.track_edges_from_surface import _boundary_edges, _build_boundary_loops, _component_analysis  # noqa: E402
from export_pitlane_surface_derived_geometry import build_minimal_trim_candidates, derive_pitlane_from_surface  # noqa: E402


DEBUG_DIR = REPO_ROOT / "data" / "debug"
CACHE_DIR = REPO_ROOT / "data" / "cache" / "tracks"

MAIN_TRACK_JSON = CACHE_DIR / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
AI_VALIDATION_JSON = DEBUG_DIR / "ai_parser_validation.json"
SOURCE_BOUNDARY_A_JSON = DEBUG_DIR / "interlagos_pitlane_surface_boundary.json"
SOURCE_DERIVED_A_JSON = DEBUG_DIR / "interlagos_pitlane_surface_derived_geometry.json"

BOUNDARY_B_JSON = DEBUG_DIR / "interlagos_pitlane_surface_boundary_transform_b.json"
BOUNDARY_B_SVG = DEBUG_DIR / "interlagos_pitlane_surface_boundary_transform_b.svg"
DERIVED_B_JSON = DEBUG_DIR / "interlagos_pitlane_surface_derived_geometry_transform_b.json"
DERIVED_B_SVG = DEBUG_DIR / "interlagos_pitlane_surface_derived_geometry_transform_b.svg"
TRIM_B_JSON = DEBUG_DIR / "interlagos_pitlane_trim_candidates_minimal_transform_b.json"
TRIM_B_SVG = DEBUG_DIR / "interlagos_pitlane_trim_candidates_minimal_transform_b.svg"
SPATIAL_B_JSON = DEBUG_DIR / "interlagos_pitlane_spatial_validation_transform_b.json"
SPATIAL_B_SVG = DEBUG_DIR / "interlagos_pitlane_spatial_validation_transform_b.svg"
REPORT_B_JSON = DEBUG_DIR / "interlagos_pitlane_transform_b_regeneration_report.json"

STRAIGHT_CURVATURE_THRESHOLD = 0.006
SENNA_SOL_FAST_LANE_START_INDEX = 100
SENNA_SOL_FAST_LANE_END_INDEX = 260

Point = Tuple[float, float]


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def round_value(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def point_xy(point: Any) -> Point:
    if isinstance(point, dict):
        return (float(point["x"]), float(point.get("y", point.get("z", 0.0))))
    return (float(point[0]), float(point[1]))


def points_xy(points: Iterable[Any]) -> List[Point]:
    return [point_xy(point) for point in points or []]


def point_payload(point: Point | Sequence[float]) -> Dict[str, float]:
    return {"x": round_value(float(point[0])), "y": round_value(float(point[1]))}


def points_payload(points: Sequence[Point]) -> List[Dict[str, float]]:
    return [point_payload(point) for point in points]


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def subtract(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def normalize(vector: Point) -> Point:
    length = math.hypot(vector[0], vector[1])
    if length <= 1e-12:
        return (0.0, 0.0)
    return (vector[0] / length, vector[1] / length)


def undirected_angle_between(a: Point, b: Point) -> float:
    na = normalize(a)
    nb = normalize(b)
    value = max(-1.0, min(1.0, dot(na, nb)))
    angle = math.degrees(math.acos(value))
    return min(angle, 180.0 - angle)


def line_direction(points: Sequence[Point]) -> Point:
    if len(points) < 2:
        return (0.0, 0.0)
    return normalize(subtract(points[-1], points[0]))


def polyline_length(points: Sequence[Point]) -> float:
    return sum(distance(points[index - 1], points[index]) for index in range(1, len(points)))


def bbox(points: Sequence[Point]) -> Dict[str, Any]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return {
        "minX": round_value(min_x),
        "maxX": round_value(max_x),
        "minY": round_value(min_y),
        "maxY": round_value(max_y),
        "width": round_value(max_x - min_x),
        "height": round_value(max_y - min_y),
        "centroid": {"x": round_value(mean(xs)), "y": round_value(mean(ys))},
    }


def signed_curvature(points: Sequence[Point], index: int) -> float:
    count = len(points)
    a = points[(index - 1) % count]
    b = points[index]
    c = points[(index + 1) % count]
    v1 = subtract(b, a)
    v2 = subtract(c, b)
    turn = math.atan2(cross(v1, v2), dot(v1, v2))
    ds = max((distance(a, b) + distance(b, c)) / 2.0, 1e-6)
    return turn / ds


def circular_runs(indices: Sequence[int], count: int) -> List[List[int]]:
    if not indices:
        return []
    runs: List[List[int]] = []
    current = [indices[0]]
    for index in indices[1:]:
        if index == current[-1] + 1:
            current.append(index)
        else:
            runs.append(current)
            current = [index]
    runs.append(current)
    if len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == count - 1:
        runs[0] = runs[-1] + runs[0]
        runs.pop()
    return runs


def circular_slice(points: Sequence[Point], run: Sequence[int]) -> List[Point]:
    return [points[index % len(points)] for index in run]


def longest_low_curvature_run(points: Sequence[Point]) -> Dict[str, Any]:
    curvatures = [abs(signed_curvature(points, index)) for index in range(len(points))]
    low_curvature_indices = [index for index, value in enumerate(curvatures) if value <= STRAIGHT_CURVATURE_THRESHOLD]
    runs = circular_runs(low_curvature_indices, len(points))
    best = max(runs, key=lambda run: polyline_length(circular_slice(points, run)))
    best_points = circular_slice(points, best)
    return {
        "startIndex": int(best[0] % len(points)),
        "endIndex": int(best[-1] % len(points)),
        "pointCount": len(best),
        "lengthMeters": round_value(polyline_length(best_points)),
        "curvatureThreshold": STRAIGHT_CURVATURE_THRESHOLD,
        "points": best_points,
    }


def nearest_point_on_segment(point: Point, a: Point, b: Point) -> Tuple[Point, float]:
    ab = subtract(b, a)
    ap = subtract(point, a)
    denom = dot(ab, ab)
    if denom <= 1e-12:
        return a, distance(point, a)
    t = max(0.0, min(1.0, dot(ap, ab) / denom))
    projected = (a[0] + ab[0] * t, a[1] + ab[1] * t)
    return projected, distance(point, projected)


def nearest_polyline_distance(point: Point, line: Sequence[Point]) -> float:
    return min(nearest_point_on_segment(point, line[index - 1], line[index])[1] for index in range(1, len(line)))


def distance_stats(points: Sequence[Point], line: Sequence[Point]) -> Dict[str, float]:
    distances = [nearest_polyline_distance(point, line) for point in points]
    ordered = sorted(distances)
    p95 = ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * 0.95) - 1))]
    return {
        "min": round_value(ordered[0]),
        "avg": round_value(mean(ordered)),
        "p95": round_value(p95),
        "max": round_value(ordered[-1]),
    }


def parse_ai_block20(path: str) -> Dict[str, Any]:
    ai_path = Path(path)
    data = ai_path.read_bytes()
    version, declared_count = struct.unpack_from("<II", data, 0)
    available = max(0, (len(data) - 16) // 20)
    count = min(int(declared_count), available)
    points: List[Point] = []
    for index in range(count):
        x, _world_y, z, _distance, _raw_index = struct.unpack_from("<3f f I", data, 16 + index * 20)
        points.append((float(x), float(z)))
    return {
        "path": str(ai_path),
        "version": int(version),
        "declaredPointCount": int(declared_count),
        "pointCount": len(points),
        "coordinateSpace": "x,z aligned to MainTrackGeometry",
        "points": points,
    }


def surface_bounds(triangles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return bbox([point_xy(vertex) for triangle in triangles for vertex in triangle.get("vertices", [])])


def triangle_area(vertices: Sequence[Sequence[float]]) -> float:
    a, b, c = (point_xy(vertex) for vertex in vertices)
    return abs(cross(subtract(b, a), subtract(c, a))) * 0.5


def recover_transform_b_triangles(source_boundary_a: Dict[str, Any]) -> List[Dict[str, Any]]:
    triangles = []
    for triangle in source_boundary_a.get("pitSurfaceTriangles", []):
        vertices = []
        for map_x, map_y in triangle.get("vertices", []):
            world_x = float(map_x)
            world_z = -float(map_y)
            vertices.append([round_value(world_x), round_value(world_z)])
        triangles.append(
            {
                "mesh": triangle.get("mesh"),
                "surface": triangle.get("surface", "PITLANE"),
                "vertices": vertices,
                "area": round_value(triangle_area(vertices)),
            }
        )
    return triangles


def enrich_minimal_trim_payload(minimal: Dict[str, Any], generated_at: str) -> Dict[str, Any]:
    payload = {
        "generatedAt": generated_at,
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "runtimeChanged": False,
        "pitLaneGeometryRawChanged": False,
        "pitLaneAiUsedForGeometry": False,
        "projection": "mapX = worldX, mapY = worldZ",
        "source": "debug_transform_b_reprojection_from_1pitlane_surface",
        "highlightedForComparisonOnly": "candidate_05_05",
        "selectedAutomatically": False,
        "readyForRuntimeIntegration": False,
    }
    payload.update(minimal)
    payload["diagnostics"] = [
        *minimal.get("diagnostics", []),
        {
            "code": "transform_b_debug_only",
            "message": "Transform B trim candidates are for manual comparison only; no candidate is selected or promoted.",
        },
    ]
    return payload


def geometry_points(geometry: Dict[str, Any], key: str) -> List[Point]:
    return points_xy(geometry.get(key, []))


def appears_in_infield(
    candidate_bbox: Dict[str, Any],
    main_bbox: Dict[str, Any],
    distance_to_straight: Dict[str, float],
    distance_to_senna_sol: Dict[str, float],
    distance_to_main: Dict[str, float],
) -> bool:
    centroid = candidate_bbox["centroid"]
    centroid_inside_main_bbox = (
        main_bbox["minX"] <= centroid["x"] <= main_bbox["maxX"]
        and main_bbox["minY"] <= centroid["y"] <= main_bbox["maxY"]
    )
    return bool(
        centroid_inside_main_bbox
        and distance_to_main["avg"] <= 35.0
        and distance_to_straight["avg"] >= 100.0
        and distance_to_senna_sol["avg"] >= 100.0
    )


def build_spatial_validation(
    derived_b: Dict[str, Any],
    old_derived_a: Dict[str, Any],
    main_track: Sequence[Point],
    fast_lane: Sequence[Point],
    pit_straight: Sequence[Point],
    senna_sol: Sequence[Point],
    mesh_triangles_b: Sequence[Dict[str, Any]],
    generated_at: str,
) -> Dict[str, Any]:
    center_b = geometry_points(derived_b, "pitCenterline")
    center_a = geometry_points(old_derived_a, "pitCenterline")
    main_bbox = bbox(main_track)
    pit_bbox_b = bbox(center_b)
    distance_to_straight = distance_stats(center_b, pit_straight)
    distance_to_senna_sol = distance_stats(center_b, senna_sol)
    distance_to_main = distance_stats(center_b, main_track)
    angle_diff = undirected_angle_between(line_direction(center_b), line_direction(pit_straight))
    infield = appears_in_infield(pit_bbox_b, main_bbox, distance_to_straight, distance_to_senna_sol, distance_to_main)
    plausible: bool | str = "uncertain"
    if distance_to_straight["avg"] <= 45.0 and distance_to_straight["p95"] <= 70.0 and angle_diff <= 5.0 and not infield:
        plausible = True
    elif distance_to_straight["avg"] >= 90.0 or angle_diff >= 15.0 or infield:
        plausible = False
    confidence = "high" if plausible is True and distance_to_straight["avg"] <= 30.0 and angle_diff <= 2.5 else "medium" if plausible is True else "low"
    reason = (
        f"Transform B places the 1pitlane* derived centerline near and parallel to the MainTrack pit straight "
        f"(avg {distance_to_straight['avg']:.2f}m, p95 {distance_to_straight['p95']:.2f}m, angle {angle_diff:.2f}deg) "
        f"and appearsInInfield={infield}. The old invalid transform A remains only as a red comparison overlay."
    )
    old_distance = distance_stats(center_a, pit_straight)
    old_angle = undirected_angle_between(line_direction(center_a), line_direction(pit_straight))

    return {
        "generatedAt": generated_at,
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": "debug_transform_b_spatial_validation",
        "debugOnly": True,
        "runtimeChanged": False,
        "geometryChanged": False,
        "authoritativeGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "selectedAutomatically": False,
        "transformUsed": "mapX = worldX, mapY = worldZ",
        "oldInvalidTransform": "mapX = worldX, mapY = -worldZ",
        "pitlaneSpatiallyPlausible": plausible,
        "distanceToMainStraightAvg": distance_to_straight["avg"],
        "distanceToMainStraightP95": distance_to_straight["p95"],
        "distanceToMainStraight": distance_to_straight,
        "distanceToSennaSolRegion": distance_to_senna_sol,
        "distanceToAnyMainTrackSegment": distance_to_main,
        "angleDiffToMainStraight": round_value(angle_diff),
        "appearsInInfield": infield,
        "confidence": confidence,
        "reason": reason,
        "oldInvalidTransformComparison": {
            "distanceToMainStraightAvg": old_distance["avg"],
            "distanceToMainStraightP95": old_distance["p95"],
            "angleDiffToMainStraight": round_value(old_angle),
        },
        "mainStraightCandidate": {
            "source": "MainTrackGeometry longest low-curvature run",
            "pointCount": len(pit_straight),
            "startPoint": point_payload(pit_straight[0]),
            "endPoint": point_payload(pit_straight[-1]),
        },
        "sennaSolCandidate": {
            "source": "fast_lane.ai x/z diagnostic segment",
            "startIndex": SENNA_SOL_FAST_LANE_START_INDEX,
            "endIndex": SENNA_SOL_FAST_LANE_END_INDEX,
            "pointCount": len(senna_sol),
            "startPoint": point_payload(senna_sol[0]),
            "endPoint": point_payload(senna_sol[-1]),
        },
        "pitLaneGeometryB": {
            "pointCount": len(center_b),
            "lengthMeters": round_value(polyline_length(center_b)),
            "bbox": pit_bbox_b,
        },
        "pitLaneSurfaceMeshesB": {
            "triangleCount": len(mesh_triangles_b),
            "bbox": surface_bounds(mesh_triangles_b),
        },
        "exports": {
            "json": str(SPATIAL_B_JSON),
            "svg": str(SPATIAL_B_SVG),
        },
    }


def svg_bounds(points: Iterable[Point], margin: float = 0.0) -> Dict[str, float]:
    values = [point for point in points if math.isfinite(point[0]) and math.isfinite(point[1])]
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    return {
        "minX": min(xs) - margin,
        "maxX": max(xs) + margin,
        "minY": min(ys) - margin,
        "maxY": max(ys) + margin,
        "width": max(xs) - min(xs) + margin * 2,
        "height": max(ys) - min(ys) + margin * 2,
    }


def map_to_svg(point: Point | Sequence[float], view: Dict[str, float], padding: float, scale: float) -> Point:
    return (
        padding + (float(point[0]) - view["minX"]) * scale,
        padding + (view["maxY"] - float(point[1])) * scale,
    )


def svg_path(points: Sequence[Point | Sequence[float]], view: Dict[str, float], padding: float, scale: float, close: bool = False) -> str:
    if not points:
        return ""
    x, y = map_to_svg(points[0], view, padding, scale)
    parts = [f"M {x:.2f} {y:.2f}"]
    for point in points[1:]:
        x, y = map_to_svg(point, view, padding, scale)
        parts.append(f"L {x:.2f} {y:.2f}")
    if close:
        parts.append("Z")
    return " ".join(parts)


def svg_label(text: str, point: Point, view: Dict[str, float], padding: float, scale: float, color: str) -> str:
    x, y = map_to_svg(point, view, padding, scale)
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.8" fill="{color}" stroke="#050816" stroke-width="1.6"/>'
        f'<text x="{x + 10:.2f}" y="{y - 8:.2f}" fill="{color}" font-size="13" font-family="Consolas, monospace" '
        f'paint-order="stroke" stroke="#050816" stroke-width="3" stroke-linejoin="round">{html.escape(text)}</text>'
    )


def make_canvas(points: Sequence[Point], *, margin: float = 72.0, target_width: int = 1500, target_height: int = 980) -> Tuple[Dict[str, float], int, int, int, float]:
    view = svg_bounds(points, margin=margin)
    padding = 52
    scale = min((target_width - padding * 2) / max(view["width"], 1.0), (target_height - padding * 2) / max(view["height"], 1.0))
    width = int(view["width"] * scale + padding * 2)
    height = int(view["height"] * scale + padding * 2)
    return view, width, height, padding, scale


def write_boundary_svg(path: Path, main_track: Sequence[Point], triangles_b: Sequence[Dict[str, Any]], loops: Sequence[Dict[str, Any]]) -> None:
    mesh_points = [point_xy(vertex) for triangle in triangles_b for vertex in triangle.get("vertices", [])]
    loop_points = [point_xy(point) for loop in loops for point in loop.get("points", [])]
    view, width, height, padding, scale = make_canvas([*main_track, *mesh_points, *loop_points])
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Interlagos PitLaneSurface transform B boundary</title>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        f'<path d="{svg_path(main_track, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.25" opacity="0.58"/>',
    ]
    for triangle in triangles_b:
        vertices = points_xy(triangle.get("vertices", []))
        lines.append(f'<path d="{svg_path(vertices, view, padding, scale, close=True)}" fill="#facc15" fill-opacity="0.075" stroke="#facc15" stroke-width="0.22" opacity="0.42"/>')
    for loop in loops:
        points = points_xy(loop.get("points", []))
        lines.append(f'<path d="{svg_path(points, view, padding, scale, close=True)}" fill="none" stroke="#facc15" stroke-width="1.8" opacity="0.86"/>')
    lines.extend(
        [
            svg_label("MainTrackGeometry", main_track[520], view, padding, scale, "#94a3b8"),
            svg_label("1pitlane* surface transform B", mesh_points[len(mesh_points) // 2], view, padding, scale, "#facc15"),
            '<text x="24" y="34" fill="#e2e8f0" font-size="15" font-family="Consolas, monospace">PitLaneSurface boundary transform B: mapX=worldX,mapY=worldZ</text>',
            '<text x="24" y="56" fill="#94a3b8" font-size="11" font-family="Consolas, monospace">debug/export only; runtime unchanged</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_derived_svg(path: Path, main_track: Sequence[Point], triangles_b: Sequence[Dict[str, Any]], derived_b: Dict[str, Any]) -> None:
    mesh_points = [point_xy(vertex) for triangle in triangles_b for vertex in triangle.get("vertices", [])]
    center = geometry_points(derived_b, "pitCenterline")
    left = geometry_points(derived_b, "pitLeftEdge")
    right = geometry_points(derived_b, "pitRightEdge")
    view, width, height, padding, scale = make_canvas([*main_track, *mesh_points, *center, *left, *right])
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Interlagos PitLaneGeometry transform B derived</title>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        f'<path d="{svg_path(main_track, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.25" opacity="0.55"/>',
    ]
    for triangle in triangles_b:
        lines.append(f'<path d="{svg_path(points_xy(triangle.get("vertices", [])), view, padding, scale, close=True)}" fill="#facc15" fill-opacity="0.06" stroke="#facc15" stroke-width="0.20" opacity="0.38"/>')
    corridor = left + list(reversed(right))
    lines.extend(
        [
            f'<path d="{svg_path(corridor, view, padding, scale, close=True)}" fill="#facc15" fill-opacity="0.16" stroke="#fde047" stroke-width="1.0" opacity="0.86"/>',
            f'<path d="{svg_path(left, view, padding, scale)}" fill="none" stroke="#38bdf8" stroke-width="1.2" opacity="0.70"/>',
            f'<path d="{svg_path(right, view, padding, scale)}" fill="none" stroke="#38bdf8" stroke-width="1.2" opacity="0.70"/>',
            f'<path d="{svg_path(center, view, padding, scale)}" fill="none" stroke="#fde047" stroke-width="4.0" opacity="0.98"/>',
            svg_label("PitLaneGeometry B", center[len(center) // 2], view, padding, scale, "#fde047"),
            '<text x="24" y="34" fill="#e2e8f0" font-size="15" font-family="Consolas, monospace">PitLaneGeometry transform B: mapX=worldX,mapY=worldZ</text>',
            '<text x="24" y="56" fill="#94a3b8" font-size="11" font-family="Consolas, monospace">debug/export only; runtime unchanged</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_trim_svg(path: Path, main_track: Sequence[Point], derived_b: Dict[str, Any], minimal_b: Dict[str, Any]) -> None:
    raw_center = geometry_points(derived_b, "pitCenterline")
    candidate_lines = {
        candidate["name"]: geometry_points(candidate, "pitCenterline")
        for candidate in minimal_b.get("candidates", [])
    }
    all_points = [*main_track, *raw_center]
    for line in candidate_lines.values():
        all_points.extend(line)
    view, width, height, padding, scale = make_canvas(all_points)
    colors = {
        "candidate_00_00": "#94a3b8",
        "candidate_05_05": "#22c55e",
        "candidate_08_08": "#38bdf8",
        "candidate_10_10": "#a855f7",
        "candidate_12_12": "#f97316",
    }
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Interlagos PitLane transform B minimal trim candidates</title>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        f'<path d="{svg_path(main_track, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.2" opacity="0.50"/>',
        f'<path d="{svg_path(raw_center, view, padding, scale)}" fill="none" stroke="#facc15" stroke-width="2.2" stroke-dasharray="8 7" opacity="0.56"/>',
    ]
    for candidate in minimal_b.get("candidates", []):
        name = candidate["name"]
        center = candidate_lines[name]
        color = colors.get(name, "#e2e8f0")
        width_line = 4.3 if name == "candidate_05_05" else 2.2
        opacity = 0.98 if name == "candidate_05_05" else 0.76
        dash = "" if name == "candidate_05_05" else ' stroke-dasharray="9 6"'
        lines.append(f'<path d="{svg_path(center, view, padding, scale)}" fill="none" stroke="{color}" stroke-width="{width_line}" opacity="{opacity}"{dash}/>')
        if center:
            lines.append(svg_label(f'{name} {candidate["removedStartMeters"]:.2f}m/{candidate["removedEndMeters"]:.2f}m', center[len(center) // 2], view, padding, scale, color))
    lines.extend(
        [
            '<text x="24" y="34" fill="#e2e8f0" font-size="15" font-family="Consolas, monospace">PitLane transform B minimal trim candidates</text>',
            '<text x="24" y="56" fill="#94a3b8" font-size="11" font-family="Consolas, monospace">candidate_05_05 is highlighted only for initial comparison; no selection made</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_spatial_svg(
    path: Path,
    main_track: Sequence[Point],
    fast_lane: Sequence[Point],
    triangles_b: Sequence[Dict[str, Any]],
    derived_b: Dict[str, Any],
    old_derived_a: Dict[str, Any],
    pit_straight: Sequence[Point],
    senna_sol: Sequence[Point],
    validation: Dict[str, Any],
) -> None:
    center_b = geometry_points(derived_b, "pitCenterline")
    center_a = geometry_points(old_derived_a, "pitCenterline")
    mesh_points = [point_xy(vertex) for triangle in triangles_b for vertex in triangle.get("vertices", [])]
    view, width, height, padding, scale = make_canvas([*main_track, *fast_lane, *mesh_points, *center_b, *center_a, *pit_straight, *senna_sol], target_width=1560, target_height=1080)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Interlagos PitLane spatial validation transform B</title>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        f'<path d="{svg_path(main_track, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.25" opacity="0.62"/>',
        f'<path d="{svg_path(fast_lane, view, padding, scale, close=True)}" fill="none" stroke="#a855f7" stroke-width="1.10" stroke-dasharray="8 7" opacity="0.72"/>',
    ]
    for triangle in triangles_b:
        lines.append(f'<path d="{svg_path(points_xy(triangle.get("vertices", [])), view, padding, scale, close=True)}" fill="#facc15" fill-opacity="0.075" stroke="#facc15" stroke-width="0.22" opacity="0.40"/>')
    lines.extend(
        [
            f'<path d="{svg_path(pit_straight, view, padding, scale)}" fill="none" stroke="#f8fafc" stroke-width="5.2" opacity="0.90"/>',
            f'<path d="{svg_path(senna_sol, view, padding, scale)}" fill="none" stroke="#22d3ee" stroke-width="4.2" opacity="0.84"/>',
            f'<path d="{svg_path(center_a, view, padding, scale)}" fill="none" stroke="#ef4444" stroke-width="3.4" opacity="0.32"/>',
            f'<path d="{svg_path(center_b, view, padding, scale)}" fill="none" stroke="#fde047" stroke-width="5.0" opacity="0.98"/>',
            svg_label("MainTrackGeometry", main_track[520], view, padding, scale, "#94a3b8"),
            svg_label("fast_lane.ai", fast_lane[870], view, padding, scale, "#a855f7"),
            svg_label("reta dos boxes", pit_straight[len(pit_straight) // 2], view, padding, scale, "#f8fafc"),
            svg_label("S do Senna / Curva do Sol", senna_sol[len(senna_sol) // 2], view, padding, scale, "#22d3ee"),
            svg_label("PitLaneGeometry B", center_b[len(center_b) // 2], view, padding, scale, "#fde047"),
            svg_label("old invalid transform", center_a[len(center_a) // 2], view, padding, scale, "#ef4444"),
            '<text x="24" y="34" fill="#e2e8f0" font-size="15" font-family="Consolas, monospace">PitLaneGeometry transform B spatial validation</text>',
            f'<text x="24" y="56" fill="#94a3b8" font-size="11" font-family="Consolas, monospace">avg={validation["distanceToMainStraightAvg"]:.2f}m p95={validation["distanceToMainStraightP95"]:.2f}m angle={validation["angleDiffToMainStraight"]:.2f}deg infield={validation["appearsInInfield"]}</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def build() -> None:
    generated_at = datetime.now(timezone.utc).isoformat()
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    source_boundary_a = read_json(SOURCE_BOUNDARY_A_JSON)
    old_derived_a = read_json(SOURCE_DERIVED_A_JSON)
    main_data = read_json(MAIN_TRACK_JSON)
    ai_data = read_json(AI_VALIDATION_JSON)

    main_track = points_xy(main_data.get("centerline", []))
    main_bbox = bbox(main_track)
    longest_straight = longest_low_curvature_run(main_track)
    pit_straight = longest_straight["points"]
    fast_ai = parse_ai_block20(ai_data["manifest"]["fastLaneAi"])
    fast_lane = fast_ai["points"]
    senna_sol = fast_lane[SENNA_SOL_FAST_LANE_START_INDEX : SENNA_SOL_FAST_LANE_END_INDEX + 1]

    triangles_b = recover_transform_b_triangles(source_boundary_a)
    components, triangle_to_component = _component_analysis(triangles_b)
    selected_component_id = components[0]["componentId"] if components else 0
    selected_indices = [index for index, component_id in triangle_to_component.items() if component_id == selected_component_id]
    boundary_edges, node_points = _boundary_edges(triangles_b, selected_indices)
    raw_loops, clean_loops = _build_boundary_loops(boundary_edges, node_points)
    selected_triangles = [triangles_b[index] for index in selected_indices]
    derived_b = derive_pitlane_from_surface(boundary_edges, selected_triangles)
    raw_center_b = geometry_points(derived_b, "pitCenterline")
    raw_length_b = round_value(polyline_length(raw_center_b))
    pit_surface_bounds_b = surface_bounds(triangles_b)
    mesh_counts: Dict[str, int] = defaultdict(int)
    for triangle in triangles_b:
        mesh_counts[str(triangle.get("mesh"))] += 1

    boundary_payload = {
        "generatedAt": generated_at,
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "runtimeChanged": False,
        "geometryChanged": False,
        "authoritativeGeometryChanged": False,
        "mainTrackGeometryChanged": False,
        "trackPhysicsGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "readyForRuntimeIntegration": False,
        "source": "PitLaneSurface 1pitlane001/1pitlane002/1pitlane003",
        "sourceTransformRecoveredFrom": str(SOURCE_BOUNDARY_A_JSON),
        "sourceVertexNote": "worldX=oldMapX and worldZ=-oldMapY recovered from the prior debug A projection; worldY is not used in this 2D map-space validation.",
        "projection": "mapX = worldX, mapY = worldZ",
        "pitSurfaceTriangles": triangles_b,
        "pitBoundaryEdges": boundary_edges,
        "pitBoundaryLoops": {"rawLoops": raw_loops, "cleanLoops": clean_loops},
        "pitSurfaceBounds": pit_surface_bounds_b,
        "components": components,
        "selectedComponentId": selected_component_id,
        "selectedTriangleIndices": selected_indices,
        "meshTriangleCounts": dict(sorted(mesh_counts.items())),
        "diagnostics": [
            {"code": "debug_only_transform_b", "message": "Transform B boundary export only; no runtime or authoritative geometry changed."}
        ],
    }

    derived_payload = {
        "generatedAt": generated_at,
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "runtimeChanged": False,
        "geometryChanged": False,
        "authoritativeGeometryChanged": False,
        "mainTrackGeometryChanged": False,
        "trackPhysicsGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "readyForRuntimeIntegration": False,
        "source": "PitLaneSurface 1pitlane001/1pitlane002/1pitlane003",
        "projection": "mapX = worldX, mapY = worldZ",
        "rawGeometrySource": str(BOUNDARY_B_JSON),
        "pitSurfaceBounds": pit_surface_bounds_b,
        "pitLeftEdge": derived_b["pitLeftEdge"],
        "pitCenterline": derived_b["pitCenterline"],
        "pitRightEdge": derived_b["pitRightEdge"],
        "pitWidth": derived_b["pitWidth"],
        "rawPointCount": len(derived_b["pitCenterline"]),
        "rawLengthMeters": raw_length_b,
        "metadata": {
            "method": derived_b["method"],
            "spacingMeters": derived_b["spacingMeters"],
            "axes": derived_b["axes"],
            "widthStats": derived_b["widthStats"],
            "pitLaneAiUsage": "not_used",
            "selectedAutomatically": False,
        },
        "samples": derived_b["samples"],
        "diagnostics": [
            *derived_b["diagnostics"],
            {"code": "debug_only_transform_b", "message": "Derived geometry uses transform B and is not connected to runtime."},
        ],
    }

    minimal_b = enrich_minimal_trim_payload(build_minimal_trim_candidates(derived_payload), generated_at)
    spatial_validation = build_spatial_validation(
        derived_payload,
        old_derived_a,
        main_track,
        fast_lane,
        pit_straight,
        senna_sol,
        triangles_b,
        generated_at,
    )

    report = {
        "generatedAt": generated_at,
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "debugOnly": True,
        "transformUsed": "mapX = worldX, mapY = worldZ",
        "sourceMeshes": ["1pitlane001", "1pitlane002", "1pitlane003"],
        "sourceVertexNote": boundary_payload["sourceVertexNote"],
        "rawPointCount": len(derived_b["pitCenterline"]),
        "rawLength": raw_length_b,
        "trimCandidates": [
            {
                "name": candidate["name"],
                "pointCount": candidate["pointCount"],
                "length": candidate["length"],
                "removedStartMeters": candidate["removedStartMeters"],
                "removedEndMeters": candidate["removedEndMeters"],
                "highlightedForComparisonOnly": candidate["name"] == "candidate_05_05",
                "selectedAutomatically": False,
            }
            for candidate in minimal_b.get("candidates", [])
        ],
        "spatialValidation": {
            "pitlaneSpatiallyPlausible": spatial_validation["pitlaneSpatiallyPlausible"],
            "distanceToMainStraightAvg": spatial_validation["distanceToMainStraightAvg"],
            "distanceToMainStraightP95": spatial_validation["distanceToMainStraightP95"],
            "angleDiffToMainStraight": spatial_validation["angleDiffToMainStraight"],
            "appearsInInfield": spatial_validation["appearsInInfield"],
            "confidence": spatial_validation["confidence"],
        },
        "oldTransformInvalidated": True,
        "runtimeChanged": False,
        "geometryChanged": False,
        "authoritativeGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "readyForRuntimeIntegration": False,
        "recommendedNextStep": "revalidate pit entry/exit using transform B geometry",
        "exports": {
            "surfaceBoundaryJson": str(BOUNDARY_B_JSON),
            "surfaceBoundarySvg": str(BOUNDARY_B_SVG),
            "derivedGeometryJson": str(DERIVED_B_JSON),
            "derivedGeometrySvg": str(DERIVED_B_SVG),
            "trimCandidatesJson": str(TRIM_B_JSON),
            "trimCandidatesSvg": str(TRIM_B_SVG),
            "spatialValidationJson": str(SPATIAL_B_JSON),
            "spatialValidationSvg": str(SPATIAL_B_SVG),
            "reportJson": str(REPORT_B_JSON),
        },
    }

    write_json(BOUNDARY_B_JSON, boundary_payload)
    write_json(DERIVED_B_JSON, derived_payload)
    write_json(TRIM_B_JSON, minimal_b)
    write_json(SPATIAL_B_JSON, spatial_validation)
    write_json(REPORT_B_JSON, report)

    write_boundary_svg(BOUNDARY_B_SVG, main_track, triangles_b, clean_loops)
    write_derived_svg(DERIVED_B_SVG, main_track, triangles_b, derived_payload)
    write_trim_svg(TRIM_B_SVG, main_track, derived_payload, minimal_b)
    write_spatial_svg(SPATIAL_B_SVG, main_track, fast_lane, triangles_b, derived_payload, old_derived_a, pit_straight, senna_sol, spatial_validation)

    print(f"Wrote {BOUNDARY_B_JSON}")
    print(f"Wrote {DERIVED_B_JSON}")
    print(f"Wrote {TRIM_B_JSON}")
    print(f"Wrote {SPATIAL_B_JSON}")
    print(f"Wrote {REPORT_B_JSON}")
    print(
        f"Transform B spatial avg={spatial_validation['distanceToMainStraightAvg']:.3f}m "
        f"p95={spatial_validation['distanceToMainStraightP95']:.3f}m "
        f"angle={spatial_validation['angleDiffToMainStraight']:.3f}deg "
        f"infield={spatial_validation['appearsInInfield']} confidence={spatial_validation['confidence']}"
    )


if __name__ == "__main__":
    build()
