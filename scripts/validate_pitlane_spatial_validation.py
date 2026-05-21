"""Debug-only spatial validation for the current PitLaneGeometry.

This script intentionally does not correct, regenerate, or promote geometry.
It compares the current PitLaneGeometry export against MainTrackGeometry,
fast_lane.ai, pit_lane.ai, and the exported 1pitlane* mesh surface.
"""
from __future__ import annotations

import html
import json
import math
import struct
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"

MAIN_TRACK_JSON = REPO_ROOT / "data" / "cache" / "tracks" / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
PITLANE_MANUAL_JSON = DEBUG_DIR / "interlagos_pitlane_trimmed_manual_05_05.json"
PITLANE_SURFACE_JSON = DEBUG_DIR / "interlagos_pitlane_surface_boundary.json"
AI_VALIDATION_JSON = DEBUG_DIR / "ai_parser_validation.json"

OUTPUT_JSON = DEBUG_DIR / "interlagos_pitlane_spatial_validation.json"
OUTPUT_SVG = DEBUG_DIR / "interlagos_pitlane_spatial_validation.svg"

STRAIGHT_CURVATURE_THRESHOLD = 0.006
SENNA_SOL_FAST_LANE_START_INDEX = 100
SENNA_SOL_FAST_LANE_END_INDEX = 260

Point = Dict[str, float]


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def point_xy(point: Any) -> Point:
    if isinstance(point, dict):
        return {"x": float(point["x"]), "y": float(point.get("y", point.get("z", 0.0)))}
    return {"x": float(point[0]), "y": float(point[1])}


def points_xy(points: Iterable[Any]) -> List[Point]:
    return [point_xy(point) for point in points or []]


def round_point(point: Point) -> Point:
    return {"x": round(point["x"], 6), "y": round(point["y"], 6)}


def distance(a: Point, b: Point) -> float:
    return math.hypot(b["x"] - a["x"], b["y"] - a["y"])


def subtract(a: Point, b: Point) -> Point:
    return {"x": a["x"] - b["x"], "y": a["y"] - b["y"]}


def dot(a: Point, b: Point) -> float:
    return a["x"] * b["x"] + a["y"] * b["y"]


def cross(a: Point, b: Point) -> float:
    return a["x"] * b["y"] - a["y"] * b["x"]


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


def bbox(points: Sequence[Point]) -> Dict[str, float]:
    xs = [point["x"] for point in points]
    ys = [point["y"] for point in points]
    return {
        "minX": round(min(xs), 6),
        "maxX": round(max(xs), 6),
        "minY": round(min(ys), 6),
        "maxY": round(max(ys), 6),
        "width": round(max(xs) - min(xs), 6),
        "height": round(max(ys) - min(ys), 6),
        "centroid": {
            "x": round(sum(xs) / len(xs), 6),
            "y": round(sum(ys) / len(ys), 6),
        },
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
        "lengthMeters": round(polyline_length(best_points), 6),
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


def parse_ai_block20(path: str, *, maintrack_coordinate_space: bool = True) -> Dict[str, Any]:
    ai_path = Path(path)
    data = ai_path.read_bytes()
    version, declared_count = struct.unpack_from("<II", data, 0)
    available = max(0, (len(data) - 16) // 20)
    count = min(int(declared_count), available)
    points: List[Point] = []
    for index in range(count):
        x, _world_y, z, _spline_distance, _raw_index = struct.unpack_from("<3f f I", data, 16 + index * 20)
        points.append({"x": float(x), "y": float(z if maintrack_coordinate_space else -z)})
    return {
        "path": str(ai_path),
        "version": int(version),
        "declaredPointCount": int(declared_count),
        "pointCount": len(points),
        "points": points,
        "coordinateSpace": "x,z aligned to MainTrackGeometry" if maintrack_coordinate_space else "x,-z diagnostic map",
    }


def line_direction(points: Sequence[Point]) -> Point:
    return normalize(subtract(points[-1], points[0]))


def mirror_y(points: Sequence[Point]) -> List[Point]:
    return [{"x": point["x"], "y": -point["y"]} for point in points]


def svg_bounds(points: Iterable[Point], margin: float = 0.0) -> Dict[str, float]:
    values = [point for point in points if math.isfinite(point["x"]) and math.isfinite(point["y"])]
    xs = [point["x"] for point in values]
    ys = [point["y"] for point in values]
    return {
        "minX": min(xs) - margin,
        "maxX": max(xs) + margin,
        "minY": min(ys) - margin,
        "maxY": max(ys) + margin,
        "width": max(xs) - min(xs) + margin * 2,
        "height": max(ys) - min(ys) + margin * 2,
    }


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


def svg_label(text: str, point: Point, view: Dict[str, float], padding: float, scale: float, color: str) -> str:
    x, y = map_to_svg(point, view, padding, scale)
    safe = html.escape(text)
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.8" fill="{color}" stroke="#050816" stroke-width="1.8"/>'
        f'<text x="{x + 10:.2f}" y="{y - 8:.2f}" fill="{color}" font-size="13" font-family="Consolas, monospace" '
        f'paint-order="stroke" stroke="#050816" stroke-width="3" stroke-linejoin="round">{safe}</text>'
    )


def write_svg(
    main_track: Sequence[Point],
    fast_lane: Sequence[Point],
    pit_lane_ai: Sequence[Point],
    pitlane: Sequence[Point],
    mesh_triangles: Sequence[Sequence[Point]],
    pit_straight: Sequence[Point],
    senna_sol: Sequence[Point],
) -> None:
    all_points: List[Point] = [*main_track, *fast_lane, *pit_lane_ai, *pitlane, *pit_straight, *senna_sol]
    for triangle in mesh_triangles:
        all_points.extend(triangle)
    view = svg_bounds(all_points, margin=72.0)
    padding = 48
    scale = min((1380 - padding * 2) / max(view["width"], 1.0), (960 - padding * 2) / max(view["height"], 1.0))
    width = int(view["width"] * scale + padding * 2)
    height = int(view["height"] * scale + padding * 2)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Interlagos PitLane spatial validation</title>",
        "<desc>Debug-only validation. No runtime or authoritative geometry changes.</desc>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        f'<path d="{svg_path(main_track, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.25" opacity="0.62"/>',
        f'<path d="{svg_path(fast_lane, view, padding, scale, close=True)}" fill="none" stroke="#a855f7" stroke-width="1.05" stroke-dasharray="8 7" opacity="0.72"/>',
        f'<path d="{svg_path(pit_lane_ai, view, padding, scale)}" fill="none" stroke="#38bdf8" stroke-width="1.15" stroke-dasharray="8 8" opacity="0.74"/>',
    ]
    for triangle in mesh_triangles:
        lines.append(
            f'<path d="{svg_path(triangle, view, padding, scale, close=True)}" fill="#facc15" fill-opacity="0.075" stroke="#facc15" stroke-width="0.25" opacity="0.42"/>'
        )
    lines.extend(
        [
            f'<path d="{svg_path(pit_straight, view, padding, scale)}" fill="none" stroke="#f8fafc" stroke-width="4.8" opacity="0.88"/>',
            f'<path d="{svg_path(senna_sol, view, padding, scale)}" fill="none" stroke="#22d3ee" stroke-width="4.0" opacity="0.86"/>',
            f'<path d="{svg_path(pitlane, view, padding, scale)}" fill="none" stroke="#fde047" stroke-width="4.6" opacity="0.98"/>',
            svg_label("MainTrack", main_track[520], view, padding, scale, "#94a3b8"),
            svg_label("fast_lane.ai", fast_lane[870], view, padding, scale, "#a855f7"),
            svg_label("pit_lane.ai", pit_lane_ai[len(pit_lane_ai) // 2], view, padding, scale, "#38bdf8"),
            svg_label("PitLaneGeometry atual", pitlane[len(pitlane) // 2], view, padding, scale, "#fde047"),
            svg_label("reta dos boxes?", pit_straight[len(pit_straight) // 2], view, padding, scale, "#f8fafc"),
            svg_label("S do Senna / Curva do Sol?", senna_sol[len(senna_sol) // 2], view, padding, scale, "#22d3ee"),
        ]
    )
    OUTPUT_SVG.write_text("\n".join([*lines, "</svg>"]), encoding="utf-8")


def build() -> None:
    main_data = read_json(MAIN_TRACK_JSON)
    pitlane_data = read_json(PITLANE_MANUAL_JSON)
    surface_data = read_json(PITLANE_SURFACE_JSON)
    ai_data = read_json(AI_VALIDATION_JSON)

    main_track = points_xy(main_data["centerline"])
    pitlane = points_xy(pitlane_data["pitCenterline"])
    main_bbox = bbox(main_track)
    pit_bbox = bbox(pitlane)

    manifest = ai_data["manifest"]
    fast_ai = parse_ai_block20(manifest["fastLaneAi"], maintrack_coordinate_space=True)
    pit_ai = parse_ai_block20(manifest["pitLaneAi"], maintrack_coordinate_space=True)
    fast_lane = fast_ai["points"]
    pit_lane_ai = pit_ai["points"]

    longest_straight = longest_low_curvature_run(main_track)
    pit_straight = longest_straight["points"]
    senna_sol = fast_lane[SENNA_SOL_FAST_LANE_START_INDEX : SENNA_SOL_FAST_LANE_END_INDEX + 1]

    mesh_triangles = [points_xy(triangle.get("vertices", [])) for triangle in surface_data.get("pitSurfaceTriangles", [])]
    mesh_counts: Dict[str, int] = {}
    for triangle in surface_data.get("pitSurfaceTriangles", []):
        mesh = str(triangle.get("mesh"))
        mesh_counts[mesh] = mesh_counts.get(mesh, 0) + 1

    distance_to_straight = distance_stats(pitlane, pit_straight)
    distance_to_senna_sol = distance_stats(pitlane, senna_sol)
    distance_to_maintrack = distance_stats(pitlane, main_track)
    mirrored_pitlane_for_diagnostic = mirror_y(pitlane)
    mirrored_distance_to_straight = distance_stats(mirrored_pitlane_for_diagnostic, pit_straight)
    mirrored_parallel_angle = min(
        angle_between(line_direction(mirrored_pitlane_for_diagnostic), line_direction(pit_straight)),
        180.0 - angle_between(line_direction(mirrored_pitlane_for_diagnostic), line_direction(pit_straight)),
    )
    parallel_angle = min(
        angle_between(line_direction(pitlane), line_direction(pit_straight)),
        180.0 - angle_between(line_direction(pitlane), line_direction(pit_straight)),
    )
    appears_parallel = parallel_angle <= 15.0
    centroid_inside_main_bbox = (
        main_bbox["minX"] <= pit_bbox["centroid"]["x"] <= main_bbox["maxX"]
        and main_bbox["minY"] <= pit_bbox["centroid"]["y"] <= main_bbox["maxY"]
    )
    appears_in_infield = (
        centroid_inside_main_bbox
        and distance_to_maintrack["avg"] <= 30.0
        and distance_to_straight["avg"] >= 100.0
        and distance_to_senna_sol["avg"] >= 100.0
    )
    plausible = "uncertain"
    if distance_to_straight["avg"] > 80.0 and distance_to_senna_sol["avg"] > 120.0:
        plausible = False
    elif distance_to_straight["avg"] < 45.0 and appears_parallel:
        plausible = True

    reason = (
        "PitLaneGeometry atual is close to some MainTrack segments but is far from the longest MainTrack straight candidate "
        f"(avg {distance_to_straight['avg']:.1f}m) and far from the S do Senna / Curva do Sol candidate "
        f"(avg {distance_to_senna_sol['avg']:.1f}m). It also is not strongly parallel to the pit straight candidate "
        f"({parallel_angle:.1f}deg). This suggests the current extracted pitlane is spatially suspicious rather than confirmed."
        if plausible is False
        else "PitLaneGeometry atual is close enough and parallel enough to the pit straight candidate for spatial plausibility."
        if plausible is True
        else "The spatial evidence is mixed; manual visual inspection is required before trusting this pitlane export."
    )
    source_diagnosis = {
        "aiGeneratedImageUsedAsGeometryReference": False,
        "aiGeneratedImageIgnored": True,
        "primaryLikelyWrongSource": "b) transformação/map-space errada",
        "secondaryLikelyWrongSource": "d) SVG/export visual invertido",
        "meshPitlaneWrongOrDisplaced": {
            "classification": "unlikely_primary",
            "reason": "PitLaneGeometry atual and 1pitlane001/002/003 surface agree with each other; the group appears displaced relative to MainTrack/fast_lane.ai, which points more to transform/map-space than to isolated mesh names.",
        },
        "mapSpaceTransformWrong": {
            "classification": "likely_primary",
            "reason": "MainTrackGeometry and fast_lane.ai align in x/z, while current PitLaneGeometry/1pitlane* exports sit on the opposite side/infield. A diagnostic y-sign mirror, not used as correction, makes the pitlane much closer and more parallel to the pit straight.",
        },
        "incorrectPitlaneComponentExtracted": {
            "classification": "less_likely",
            "reason": "The extracted component is from explicitly named 1pitlane001/002/003 meshes and is internally coherent.",
        },
        "svgExportVisualInverted": {
            "classification": "possible_symptom",
            "reason": "The visual mismatch is consistent with an axis/sign inversion; because the exported PitLaneGeometry coordinates themselves carry that position, it is not treated as SVG-only until proven otherwise.",
        },
        "previousVisualInterpretationWrong": {
            "classification": "possible_consequence",
            "reason": "Earlier visual plausibility can be explained by comparing layers in inconsistent map-space conventions.",
        },
        "diagnosticMirrorYOnlyNotCorrection": {
            "distancePitLaneToPitStraightAfterMirror": mirrored_distance_to_straight,
            "parallelAngleAfterMirrorDeg": round(mirrored_parallel_angle, 6),
            "usedForCorrection": False,
        },
    }

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": "debug_pitlane_spatial_validation",
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "mainTrackGeometryChanged": False,
        "trackPhysicsGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "selectedAutomatically": False,
        "coordinateNote": "MainTrackGeometry uses x/z. AI splines are plotted as x/z to align with MainTrack. PitLaneGeometry and 1pitlane* meshes are plotted exactly as currently exported.",
        "pitLaneGeometryBBox": pit_bbox,
        "mainTrackBBox": main_bbox,
        "longestMainTrackStraightCandidate": {
            "startIndex": longest_straight["startIndex"],
            "endIndex": longest_straight["endIndex"],
            "pointCount": longest_straight["pointCount"],
            "lengthMeters": longest_straight["lengthMeters"],
            "curvatureThreshold": longest_straight["curvatureThreshold"],
            "startPoint": round_point(pit_straight[0]),
            "endPoint": round_point(pit_straight[-1]),
        },
        "sennaSolCandidate": {
            "source": "fast_lane.ai x/z diagnostic segment",
            "startIndex": SENNA_SOL_FAST_LANE_START_INDEX,
            "endIndex": SENNA_SOL_FAST_LANE_END_INDEX,
            "pointCount": len(senna_sol),
            "startPoint": round_point(senna_sol[0]),
            "endPoint": round_point(senna_sol[-1]),
        },
        "distancePitLaneToLongestMainTrackStraight": distance_to_straight,
        "distancePitLaneToSennaSolCandidate": distance_to_senna_sol,
        "distancePitLaneToAnyMainTrackSegment": distance_to_maintrack,
        "pitLaneAppearsParallelToPitStraight": appears_parallel,
        "parallelAngleDeg": round(parallel_angle, 6),
        "pitLaneAppearsInInfield": appears_in_infield,
        "pitlaneSpatiallyPlausible": plausible,
        "reason": reason,
        "sourceDiagnosis": source_diagnosis,
        "aiFiles": {
            "fastLaneAi": {
                "path": fast_ai["path"],
                "pointCount": fast_ai["pointCount"],
                "coordinateSpace": fast_ai["coordinateSpace"],
            },
            "pitLaneAi": {
                "path": pit_ai["path"],
                "pointCount": pit_ai["pointCount"],
                "coordinateSpace": pit_ai["coordinateSpace"],
                "usedAsOverlayOnly": True,
            },
        },
        "pitLaneSurfaceMeshes": {
            "source": "current exported 1pitlane001/002/003 debug surface",
            "triangleCount": len(mesh_triangles),
            "meshTriangleCounts": mesh_counts,
        },
        "exports": {"json": str(OUTPUT_JSON), "svg": str(OUTPUT_SVG)},
    }
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_svg(main_track, fast_lane, pit_lane_ai, pitlane, mesh_triangles, pit_straight, senna_sol)
    print(OUTPUT_JSON)
    print(OUTPUT_SVG)


if __name__ == "__main__":
    build()
