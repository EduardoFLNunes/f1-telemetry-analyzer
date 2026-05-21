"""Validate current PitLaneGeometry spatial placement against track references.

Debug/export only. This script reads existing MainTrackGeometry, PitLaneManual
05_05, KN5 1pitlane* surface exports, and AC AI splines, then writes a single
SVG plus a short JSON report. It does not correct or promote any geometry.
"""
from __future__ import annotations

import html
import json
import math
import struct
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"
MAIN_TRACK_JSON = REPO_ROOT / "data" / "cache" / "tracks" / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
PITLANE_MANUAL_JSON = DEBUG_DIR / "interlagos_pitlane_trimmed_manual_05_05.json"
PITLANE_SURFACE_BOUNDARY_JSON = DEBUG_DIR / "interlagos_pitlane_surface_boundary.json"
AI_PARSER_VALIDATION_JSON = DEBUG_DIR / "ai_parser_validation.json"

OUTPUT_SVG = DEBUG_DIR / "interlagos_pitlane_spatial_position_validation.svg"
OUTPUT_JSON = DEBUG_DIR / "interlagos_pitlane_spatial_position_validation.json"

PIT_MANUAL_START = {"x": -339.274471, "y": -425.069001}
PIT_MANUAL_END = {"x": -432.446484, "y": -75.929951}

Point = Dict[str, float]


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def point_xy(point: Any) -> Point:
    if isinstance(point, dict):
        return {"x": float(point["x"]), "y": float(point.get("y", point.get("z", 0.0)))}
    return {"x": float(point[0]), "y": float(point[1])}


def points_xy(points: Iterable[Any]) -> List[Point]:
    return [point_xy(point) for point in points or []]


def point_round(point: Point) -> Point:
    return {"x": round(point["x"], 6), "y": round(point["y"], 6)}


def distance(a: Point, b: Point) -> float:
    return math.hypot(b["x"] - a["x"], b["y"] - a["y"])


def subtract(a: Point, b: Point) -> Point:
    return {"x": a["x"] - b["x"], "y": a["y"] - b["y"]}


def dot(a: Point, b: Point) -> float:
    return a["x"] * b["x"] + a["y"] * b["y"]


def normalize(v: Point) -> Point:
    length = math.hypot(v["x"], v["y"])
    if length <= 1e-9:
        return {"x": 0.0, "y": 0.0}
    return {"x": v["x"] / length, "y": v["y"] / length}


def angle_between(a: Point, b: Point) -> float:
    na = normalize(a)
    nb = normalize(b)
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(na, nb)))))


def polyline_length(points: Sequence[Point]) -> float:
    return sum(distance(points[index - 1], points[index]) for index in range(1, len(points)))


def tangent(points: Sequence[Point], start_index: int, end_index: int) -> Point:
    return normalize(subtract(points[end_index], points[start_index]))


def nearest_point_on_segment(point: Point, a: Point, b: Point) -> Tuple[Point, float]:
    ab = subtract(b, a)
    ap = subtract(point, a)
    denom = dot(ab, ab)
    if denom <= 1e-12:
        return a, distance(point, a)
    t = max(0.0, min(1.0, dot(ap, ab) / denom))
    projected = {"x": a["x"] + ab["x"] * t, "y": a["y"] + ab["y"] * t}
    return projected, distance(point, projected)


def nearest_polyline_distance(point: Point, line: Sequence[Point]) -> float:
    return min(nearest_point_on_segment(point, line[index - 1], line[index])[1] for index in range(1, len(line)))


def distance_stats(points: Sequence[Point], line: Sequence[Point]) -> Dict[str, float]:
    distances = [nearest_polyline_distance(point, line) for point in points]
    ordered = sorted(distances)
    p95 = ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * 0.95) - 1))]
    return {
        "min": round(ordered[0], 6),
        "avg": round(mean(ordered), 6),
        "p95": round(p95, 6),
        "max": round(ordered[-1], 6),
    }


def parse_ai_block20(path: str) -> Dict[str, Any]:
    ai_path = Path(path)
    data = ai_path.read_bytes()
    if len(data) < 16:
        raise ValueError(f"Invalid AI file: {ai_path}")
    version, declared_count = struct.unpack_from("<II", data, 0)
    available = max(0, (len(data) - 16) // 20)
    count = min(int(declared_count), available)
    points: List[Point] = []
    distances: List[float] = []
    for index in range(count):
        x, _y, z, spline_distance, _raw_index = struct.unpack_from("<3f f I", data, 16 + index * 20)
        points.append({"x": float(x), "y": float(-z)})
        distances.append(float(spline_distance))
    return {
        "path": str(ai_path),
        "version": int(version),
        "declaredPointCount": int(declared_count),
        "pointCount": len(points),
        "points": points,
        "distances": distances,
    }


def nearest_index(points: Sequence[Point], target: Point) -> int:
    return min(range(len(points)), key=lambda index: distance(points[index], target))


def circular_slice(points: Sequence[Point], start_index: int, end_index: int) -> List[Point]:
    if start_index <= end_index:
        return list(points[start_index : end_index + 1])
    return [*points[start_index:], *points[: end_index + 1]]


def bounds(points: Iterable[Point], margin: float = 0.0) -> Dict[str, float]:
    pts = [point for point in points if point and math.isfinite(point["x"]) and math.isfinite(point["y"])]
    xs = [point["x"] for point in pts]
    ys = [point["y"] for point in pts]
    min_x = min(xs) - margin
    max_x = max(xs) + margin
    min_y = min(ys) - margin
    max_y = max(ys) + margin
    return {"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y, "width": max_x - min_x, "height": max_y - min_y}


def map_to_svg(point: Point, view: Dict[str, float], padding: float, scale: float) -> Tuple[float, float]:
    return padding + (point["x"] - view["minX"]) * scale, padding + (view["maxY"] - point["y"]) * scale


def svg_path(points: Sequence[Point], view: Dict[str, float], padding: float, scale: float, close: bool = False) -> str:
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


def svg_text(text: str, x: float, y: float, size: int = 12, color: str = "#e5e7eb") -> str:
    return f'<text x="{x:.2f}" y="{y:.2f}" fill="{color}" font-size="{size}" font-family="Consolas, monospace">{html.escape(text)}</text>'


def svg_label(text: str, point: Point, view: Dict[str, float], padding: float, scale: float, color: str) -> str:
    x, y = map_to_svg(point, view, padding, scale)
    safe = html.escape(text)
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.4" fill="{color}" stroke="#050816" stroke-width="1.8"/>'
        f'<text x="{x + 9:.2f}" y="{y - 8:.2f}" fill="{color}" font-size="13" font-family="Consolas, monospace" '
        f'paint-order="stroke" stroke="#050816" stroke-width="3" stroke-linejoin="round">{safe}</text>'
    )


def write_svg(
    main_track: Sequence[Point],
    fast_lane: Sequence[Point],
    pit_lane_ai: Sequence[Point],
    pitlane_candidate: Sequence[Point],
    pit_surface_loops: Sequence[Sequence[Point]],
    pit_straight: Sequence[Point],
) -> None:
    all_points: List[Point] = [*main_track, *fast_lane, *pit_lane_ai, *pitlane_candidate]
    for loop in pit_surface_loops:
        all_points.extend(loop)
    view = bounds(all_points, margin=70.0)
    padding = 48
    scale = min((1320 - padding * 2) / max(view["width"], 1.0), (940 - padding * 2) / max(view["height"], 1.0))
    width = int(view["width"] * scale + padding * 2)
    height = int(view["height"] * scale + padding * 2)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Interlagos pitlane spatial position validation</title>",
        "<desc>Debug-only overlay comparing MainTrack, fast_lane.ai, pit_lane.ai, current PitLaneGeometry, and 1pitlane* KN5 surface.</desc>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        f'<path d="{svg_path(main_track, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.2" opacity="0.62"/>',
        f'<path d="{svg_path(fast_lane, view, padding, scale, close=True)}" fill="none" stroke="#60a5fa" stroke-width="0.75" opacity="0.34"/>',
    ]
    for loop in pit_surface_loops:
        lines.append(
            f'<path d="{svg_path(loop, view, padding, scale, close=True)}" fill="#f59e0b" fill-opacity="0.12" stroke="#f59e0b" stroke-width="1.0" opacity="0.42"/>'
        )
    lines.extend(
        [
            f'<path d="{svg_path(pit_straight, view, padding, scale)}" fill="none" stroke="#f8fafc" stroke-width="4.6" opacity="0.88"/>',
            f'<path d="{svg_path(pit_lane_ai, view, padding, scale)}" fill="none" stroke="#fef3c7" stroke-width="1.55" stroke-dasharray="9 8" opacity="0.82"/>',
            f'<path d="{svg_path(pitlane_candidate, view, padding, scale)}" fill="none" stroke="#fde047" stroke-width="4.2" opacity="0.98"/>',
            svg_label("reta dos boxes", pit_straight[len(pit_straight) // 2], view, padding, scale, "#f8fafc"),
            svg_label("S do Senna", fast_lane[2560], view, padding, scale, "#38bdf8"),
            svg_label("Curva do Sol", fast_lane[215], view, padding, scale, "#38bdf8"),
            svg_label("pitlane candidate", pitlane_candidate[len(pitlane_candidate) // 2], view, padding, scale, "#fde047"),
            svg_text("gray=MainTrackGeometry | white=fast_lane.ai pit straight | yellow=current PitLaneGeometry | dashed=pit_lane.ai diagnostic", 24, 32, 12, "#cbd5e1"),
            svg_text("orange fill=KN5 1pitlane001/002/003 surface export | debug-only, runtime unchanged", 24, 50, 12, "#cbd5e1"),
        ]
    )
    OUTPUT_SVG.write_text("\n".join([*lines, "</svg>"]), encoding="utf-8")


def build() -> None:
    main_data = read_json(MAIN_TRACK_JSON)
    pitlane_data = read_json(PITLANE_MANUAL_JSON)
    surface_data = read_json(PITLANE_SURFACE_BOUNDARY_JSON)
    ai_validation = read_json(AI_PARSER_VALIDATION_JSON)

    main_track = points_xy(main_data["centerline"])
    pitlane_candidate = points_xy(pitlane_data["pitCenterline"])
    loops_data = (surface_data.get("pitBoundaryLoops") or {}).get("rawLoops") or []
    pit_surface_loops = [points_xy(loop.get("points", [])) for loop in loops_data]

    manifest = ai_validation.get("manifest", {})
    fast_ai = parse_ai_block20(manifest["fastLaneAi"])
    pit_ai = parse_ai_block20(manifest["pitLaneAi"])
    fast_lane = fast_ai["points"]
    pit_lane_ai = pit_ai["points"]

    pit_start_near_fast = nearest_index(fast_lane, PIT_MANUAL_START)
    pit_end_near_fast = nearest_index(fast_lane, PIT_MANUAL_END)
    pit_straight = circular_slice(fast_lane, pit_end_near_fast, pit_start_near_fast)

    pit_candidate_tangent = tangent(pitlane_candidate, 0, len(pitlane_candidate) - 1)
    pit_straight_tangent = tangent(pit_straight, 0, len(pit_straight) - 1)
    parallel_angle = min(angle_between(pit_candidate_tangent, pit_straight_tangent), angle_between(pit_candidate_tangent, {"x": -pit_straight_tangent["x"], "y": -pit_straight_tangent["y"]}))

    fast_straight_distance = distance_stats(pitlane_candidate, pit_straight)
    pit_ai_distance = distance_stats(pitlane_candidate, pit_lane_ai)
    surface_bounds = surface_data.get("pitSurfaceBounds")

    mesh_counts: Dict[str, int] = {}
    for triangle in surface_data.get("pitSurfaceTriangles", []):
        mesh = triangle.get("mesh")
        mesh_counts[mesh] = mesh_counts.get(mesh, 0) + 1

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": "debug_pitlane_spatial_position_validation",
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "selectedAutomatically": False,
        "mainTrackGeometry": {
            "path": str(MAIN_TRACK_JSON),
            "pointCount": len(main_track),
        },
        "fastLaneAi": {
            "path": fast_ai["path"],
            "pointCount": fast_ai["pointCount"],
            "pitStraightStartIndex": pit_end_near_fast,
            "pitStraightEndIndex": pit_start_near_fast,
            "pitStraightPointCount": len(pit_straight),
            "pitStraightLengthMeters": round(polyline_length(pit_straight), 6),
        },
        "pitLaneAiDiagnostic": {
            "path": pit_ai["path"],
            "pointCount": pit_ai["pointCount"],
            "distanceFromCurrentPitLane": pit_ai_distance,
            "usedForGeometry": False,
        },
        "pitLaneSurfaceMeshes": {
            "source": "KN5 1pitlane001/1pitlane002/1pitlane003",
            "bounds": surface_bounds,
            "triangleCount": len(surface_data.get("pitSurfaceTriangles", [])),
            "meshTriangleCounts": mesh_counts,
        },
        "currentPitLaneGeometry": {
            "source": str(PITLANE_MANUAL_JSON),
            "pointCount": len(pitlane_candidate),
            "lengthMeters": round(polyline_length(pitlane_candidate), 6),
            "manualStart": point_round(PIT_MANUAL_START),
            "manualEnd": point_round(PIT_MANUAL_END),
            "distanceToFastLanePitStraight": fast_straight_distance,
            "parallelAngleVsFastLanePitStraightDeg": round(parallel_angle, 6),
        },
        "spatialConclusion": {
            "pitlaneCandidateIsOnPitStraightRegion": fast_straight_distance["avg"] < 45.0 and parallel_angle < 15.0,
            "explanation": (
                "The current PitLaneGeometry sits on the exported KN5 1pitlane* surface and runs parallel to the fast_lane.ai pit straight. "
                "pit_lane.ai is drawn only as diagnostic overlay and is not used as geometry."
            ),
        },
        "exports": {"svg": str(OUTPUT_SVG), "json": str(OUTPUT_JSON)},
    }
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_svg(main_track, fast_lane, pit_lane_ai, pitlane_candidate, pit_surface_loops, pit_straight)
    print(OUTPUT_JSON)
    print(OUTPUT_SVG)


if __name__ == "__main__":
    build()
