"""Create debug-only analysis for Interlagos pit exit transition geometry.

This script reads existing debug/cache JSON artifacts. It does not alter the
authoritative MainTrackGeometry, TrackPhysicsGeometry, pitlane geometry, or
runtime state.
"""
from __future__ import annotations

import html
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"
MAIN_TRACK_CACHE = REPO_ROOT / "data" / "cache" / "tracks" / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"


Point = Dict[str, float]


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def point_xy(point: Dict[str, Any]) -> Point:
    return {"x": float(point["x"]), "y": float(point.get("y", point.get("z", 0.0)))}


def points_xy(points: Iterable[Dict[str, Any]]) -> List[Point]:
    return [point_xy(point) for point in points]


def distance(a: Point, b: Point) -> float:
    return math.hypot(b["x"] - a["x"], b["y"] - a["y"])


def subtract(a: Point, b: Point) -> Point:
    return {"x": a["x"] - b["x"], "y": a["y"] - b["y"]}


def add(a: Point, b: Point) -> Point:
    return {"x": a["x"] + b["x"], "y": a["y"] + b["y"]}


def scale_vector(v: Point, scale: float) -> Point:
    return {"x": v["x"] * scale, "y": v["y"] * scale}


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


def angle_diff(a: float, b: float) -> float:
    return abs(math.atan2(math.sin(b - a), math.cos(b - a)))


def heading(a: Point, b: Point) -> float:
    return math.atan2(b["y"] - a["y"], b["x"] - a["x"])


def tangent(points: List[Point], index: int, span: int = 4) -> Point:
    start = points[max(0, index - span)]
    end = points[min(len(points) - 1, index + span)]
    return normalize(subtract(end, start))


def signed_curvature(points: List[Point], index: int) -> float:
    a = points[(index - 1) % len(points)]
    b = points[index]
    c = points[(index + 1) % len(points)]
    v1 = subtract(b, a)
    v2 = subtract(c, b)
    angle = math.atan2(cross(v1, v2), dot(v1, v2))
    ds = max((distance(a, b) + distance(b, c)) / 2.0, 1e-6)
    return angle / ds


def nearest_point_on_segment(point: Point, a: Point, b: Point) -> Tuple[Point, float, float]:
    ab = subtract(b, a)
    ap = subtract(point, a)
    denom = dot(ab, ab)
    if denom <= 1e-12:
        return a, 0.0, distance(point, a)
    t = max(0.0, min(1.0, dot(ap, ab) / denom))
    projected = add(a, scale_vector(ab, t))
    return projected, t, distance(point, projected)


def nearest_polyline(point: Point, line: List[Point]) -> Dict[str, Any]:
    best: Optional[Dict[str, Any]] = None
    for index in range(1, len(line)):
        projected, t, dist = nearest_point_on_segment(point, line[index - 1], line[index])
        if best is None or dist < best["distance"]:
            best = {"index": index - 1, "t": t, "point": projected, "distance": dist}
    return best or {"index": 0, "t": 0.0, "point": line[0], "distance": distance(point, line[0])}


def contiguous_runs(indices: List[int]) -> List[List[int]]:
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
    return runs


def polyline_length(points: List[Point]) -> float:
    return sum(distance(points[index - 1], points[index]) for index in range(1, len(points)))


def cubic_hermite(a: Point, b: Point, tangent_a: Point, tangent_b: Point, count: int, tension: float = 0.55) -> List[Point]:
    chord = distance(a, b)
    m0 = scale_vector(tangent_a, chord * tension)
    m1 = scale_vector(tangent_b, chord * tension)
    out = []
    for index in range(count):
        t = index / max(count - 1, 1)
        t2 = t * t
        t3 = t2 * t
        h00 = 2 * t3 - 3 * t2 + 1
        h10 = t3 - 2 * t2 + t
        h01 = -2 * t3 + 3 * t2
        h11 = t3 - t2
        out.append(
            {
                "x": h00 * a["x"] + h10 * m0["x"] + h01 * b["x"] + h11 * m1["x"],
                "y": h00 * a["y"] + h10 * m0["y"] + h01 * b["y"] + h11 * m1["y"],
            }
        )
    return out


def bezier(p0: Point, p1: Point, p2: Point, p3: Point, count: int) -> List[Point]:
    out = []
    for index in range(count):
        t = index / max(count - 1, 1)
        u = 1 - t
        out.append(
            {
                "x": u**3 * p0["x"] + 3 * u * u * t * p1["x"] + 3 * u * t * t * p2["x"] + t**3 * p3["x"],
                "y": u**3 * p0["y"] + 3 * u * u * t * p1["y"] + 3 * u * t * t * p2["y"] + t**3 * p3["y"],
            }
        )
    return out


def bounds(points: Iterable[Point], margin: float = 0.0) -> Dict[str, float]:
    pts = [point for point in points if point]
    xs = [point["x"] for point in pts]
    ys = [point["y"] for point in pts]
    min_x = min(xs) - margin
    max_x = max(xs) + margin
    min_y = min(ys) - margin
    max_y = max(ys) + margin
    return {"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y, "width": max_x - min_x, "height": max_y - min_y}


def map_to_svg(point: Point, view: Dict[str, float], padding: float, scale: float) -> Tuple[float, float]:
    return padding + (point["x"] - view["minX"]) * scale, padding + (view["maxY"] - point["y"]) * scale


def path(points: List[Point], view: Dict[str, float], padding: float, scale: float, close: bool = False) -> str:
    if not points:
        return ""
    x, y = map_to_svg(points[0], view, padding, scale)
    commands = [f"M {x:.2f} {y:.2f}"]
    for point in points[1:]:
        x, y = map_to_svg(point, view, padding, scale)
        commands.append(f"L {x:.2f} {y:.2f}")
    if close:
        commands.append("Z")
    return " ".join(commands)


def corridor(left: List[Point], right: List[Point], view: Dict[str, float], padding: float, scale: float) -> str:
    return path([*left, *reversed(right)], view, padding, scale, close=True)


def svg_text(text: str, x: float, y: float, size: int = 11, color: str = "#e5e7eb") -> str:
    return f'<text x="{x:.2f}" y="{y:.2f}" fill="{color}" font-size="{size}" font-family="Consolas, monospace">{html.escape(text)}</text>'


def svg_marker(label: str, point: Point, view: Dict[str, float], padding: float, scale: float, color: str) -> str:
    x, y = map_to_svg(point, view, padding, scale)
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="{color}" stroke="#020617" stroke-width="2"/>'
        + svg_text(label, x + 9, y - 8, 10, color)
    )


def svg_canvas(view: Dict[str, float], title: str, max_width: int = 1240, max_height: int = 920) -> Tuple[int, int, float, int, List[str]]:
    padding = 44
    scale = min((max_width - padding * 2) / max(view["width"], 1), (max_height - padding * 2) / max(view["height"], 1))
    width = int(view["width"] * scale + padding * 2)
    height = int(view["height"] * scale + padding * 2)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#050816"/>',
        svg_text(title, 22, 30, 16, "#f8fafc"),
        svg_text("debug-only: runtimeChanged=false, canonical map-space unchanged", 22, height - 18, 10, "#94a3b8"),
    ]
    return width, height, scale, padding, lines


def write_svg(output: Path, lines: List[str]) -> None:
    output.write_text("\n".join([*lines, "</svg>"]), encoding="utf-8")


def build() -> None:
    main = read_json(MAIN_TRACK_CACHE)
    manual = read_json(DEBUG_DIR / "interlagos_pitlane_trimmed_manual_05_05.json")

    main_center = points_xy(main["centerline"])
    main_left = points_xy(main["boundsLeft"])
    main_right = points_xy(main["boundsRight"])
    main_width = [float(width) for width in main.get("localWidth", [])]
    pit_center = points_xy(manual["pitCenterline"])
    pit_left = points_xy(manual["pitLeftEdge"])
    pit_right = points_xy(manual["pitRightEdge"])
    pit_exit = pit_center[-1]
    pit_exit_tangent = tangent(pit_center, len(pit_center) - 1)

    radius = 80.0
    spatial_indices = [index for index, point in enumerate(main_center) if distance(point, pit_exit) <= radius]
    runs = contiguous_runs(spatial_indices)
    nearest_main = nearest_polyline(pit_exit, main_center)

    curvatures = [signed_curvature(main_center, index) for index in range(len(main_center))]
    headings = [heading(main_center[(index - 1) % len(main_center)], main_center[(index + 1) % len(main_center)]) for index in range(len(main_center))]

    run_reports = []
    for run in runs:
        signs = []
        for index in run[1:-1]:
            curv = curvatures[index]
            signs.append(1 if curv > 0.001 else -1 if curv < -0.001 else 0)
        sign_changes = sum(1 for index in range(1, len(signs)) if signs[index] and signs[index - 1] and signs[index] != signs[index - 1])
        run_reports.append(
            {
                "startIndex": run[0],
                "endIndex": run[-1],
                "pointCount": len(run),
                "minDistanceToPitExit": min(distance(main_center[index], pit_exit) for index in run),
                "maxDistanceToPitExit": max(distance(main_center[index], pit_exit) for index in run),
                "maxAbsCurvature": max(abs(curvatures[index]) for index in run),
                "avgAbsCurvature": mean(abs(curvatures[index]) for index in run),
                "headingChangeDeg": math.degrees(sum(angle_diff(headings[index - 1], headings[index]) for index in run[1:])),
                "widthMin": min(main_width[index] for index in run),
                "widthAvg": mean(main_width[index] for index in run),
                "widthMax": max(main_width[index] for index in run),
                "curvatureSignChanges": sign_changes,
            }
        )

    chicane_run = max(run_reports, key=lambda item: (item["curvatureSignChanges"], -item["minDistanceToPitExit"], item["maxAbsCurvature"]))
    chicane_indices = list(range(chicane_run["startIndex"], chicane_run["endIndex"] + 1))
    sign_change_core = []
    for index in chicane_indices[1:-1]:
        previous = curvatures[index - 1]
        current = curvatures[index]
        if previous * current < 0:
            sign_change_core.append(index)
    if sign_change_core:
        suspect_start = max(chicane_run["startIndex"], min(sign_change_core) - 8)
        suspect_end = min(chicane_run["endIndex"], max(sign_change_core) + 8)
    else:
        top_index = max(chicane_indices, key=lambda index: abs(curvatures[index]))
        suspect_start = max(chicane_run["startIndex"], top_index - 16)
        suspect_end = min(chicane_run["endIndex"], top_index + 16)
    suspect_indices = list(range(suspect_start, suspect_end + 1))

    direction_candidates = []
    for index in spatial_indices:
        main_tangent = tangent(main_center, index)
        direction_diff = angle_between(pit_exit_tangent, main_tangent)
        if direction_diff <= 45.0:
            direction_candidates.append(
                {
                    "index": index,
                    "point": main_center[index],
                    "distance": distance(pit_exit, main_center[index]),
                    "directionDiffDeg": direction_diff,
                }
            )
    merge = min(direction_candidates, key=lambda item: item["distance"]) if direction_candidates else {
        "index": int(nearest_main["index"]),
        "point": nearest_main["point"],
        "distance": nearest_main["distance"],
        "directionDiffDeg": angle_between(pit_exit_tangent, tangent(main_center, int(nearest_main["index"]))),
    }

    anchor_start = max(0, suspect_start - 8)
    anchor_end = min(len(main_center) - 1, suspect_end + 8)
    original_segment = main_center[anchor_start : anchor_end + 1]
    candidate_segment = cubic_hermite(
        main_center[anchor_start],
        main_center[anchor_end],
        tangent(main_center, anchor_start, span=8),
        tangent(main_center, anchor_end, span=8),
        len(original_segment),
    )
    max_displacement = max(distance(original, candidate) for original, candidate in zip(original_segment, candidate_segment))

    transition_start = pit_exit
    transition_end = merge["point"]
    transition_length_hint = distance(transition_start, transition_end)
    transition_p1 = add(transition_start, scale_vector(pit_exit_tangent, transition_length_hint * 0.42))
    transition_p2 = add(transition_end, scale_vector(tangent(main_center, merge["index"]), -transition_length_hint * 0.42))
    transition_center = bezier(transition_start, transition_p1, transition_p2, transition_end, 32)

    zone_widths = [main_width[index] for index in spatial_indices]
    zone_heading_change = math.degrees(sum(angle_diff(headings[index - 1], headings[index]) for index in spatial_indices[1:] if index - 1 in spatial_indices))

    analysis = {
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": "debug_local_pit_exit_analysis",
        "runtimeChanged": False,
        "readyForRuntimeIntegration": False,
        "canonicalMapSpaceChanged": False,
        "pitManualEnd": pit_exit,
        "radiusMeters": radius,
        "nearestMainPoint": nearest_main,
        "nearestPitExitDistance": nearest_main["distance"],
        "directionCompatibleMergePoint": merge,
        "spatialRuns": run_reports,
        "suspectedFalseChicaneStartIndex": suspect_start,
        "suspectedFalseChicaneEndIndex": suspect_end,
        "suspectedFalseChicaneIndices": suspect_indices,
        "maxCurvatureSpike": max(abs(curvatures[index]) for index in suspect_indices),
        "widthVariationInZone": max(zone_widths) - min(zone_widths),
        "headingChangeInZone": zone_heading_change,
        "localMainTrackSamples": [
            {
                "index": index,
                "point": main_center[index],
                "distanceToPitExit": distance(main_center[index], pit_exit),
                "width": main_width[index],
                "curvature": curvatures[index],
                "headingDeg": math.degrees(headings[index]),
                "suspectedFalseChicane": index in suspect_indices,
            }
            for index in spatial_indices
        ],
        "diagnostics": [
            {
                "code": "debug_only",
                "message": "Analysis only; MainTrackGeometry and runtime projection are unchanged.",
            },
            {
                "code": "two_maintrack_runs_near_pit_exit",
                "message": "The nearest main-track branch is not direction-compatible with pit exit; transition candidate uses the closest direction-compatible main-track point.",
            },
        ],
    }

    candidate = {
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": "debug_maintrack_exit_zone_candidate",
        "runtimeChanged": False,
        "readyForRuntimeIntegration": False,
        "authoritativeGeometryChanged": False,
        "suspectedFalseChicaneStartIndex": suspect_start,
        "suspectedFalseChicaneEndIndex": suspect_end,
        "anchorStartIndex": anchor_start,
        "anchorEndIndex": anchor_end,
        "originalSegment": original_segment,
        "candidateSegment": candidate_segment,
        "maxCorrectionDisplacement": max_displacement,
        "method": "local_cubic_hermite_between_existing_maintrack_anchors",
    }

    transition = {
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": "debug_local_transition",
        "runtimeChanged": False,
        "readyForRuntimeIntegration": False,
        "startPitPoint": transition_start,
        "endMainMergePoint": transition_end,
        "endMainMergeIndex": merge["index"],
        "mergeSelection": "nearest_direction_compatible_maintrack_point_within_80m",
        "mergeDistanceMeters": merge["distance"],
        "mergeDirectionDiffDeg": merge["directionDiffDeg"],
        "controlPoints": [transition_start, transition_p1, transition_p2, transition_end],
        "centerline": transition_center,
        "length": polyline_length(transition_center),
    }

    (DEBUG_DIR / "interlagos_pit_exit_core_problem_analysis.json").write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    (DEBUG_DIR / "interlagos_maintrack_pit_exit_zone_candidate.json").write_text(json.dumps(candidate, indent=2), encoding="utf-8")
    (DEBUG_DIR / "interlagos_pit_exit_transition_geometry.json").write_text(json.dumps(transition, indent=2), encoding="utf-8")

    zone_points = [
        *[main_center[index] for index in spatial_indices],
        *pit_center[-45:],
        *pit_left[-45:],
        *pit_right[-45:],
        *candidate_segment,
        *transition_center,
    ]
    view = bounds(zone_points, margin=34.0)

    width, height, svg_scale, padding, lines = svg_canvas(view, "Interlagos Pit Exit Core Problem Analysis")
    lines.extend(
        [
            f'<path d="{corridor(main_left, main_right, view, padding, svg_scale)}" fill="#64748b" opacity="0.10"/>',
            f'<path d="{path(main_center, view, padding, svg_scale, close=True)}" fill="none" stroke="#a78bfa" stroke-width="1.2" opacity="0.7"/>',
            f'<path d="{path(main_left, view, padding, svg_scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="0.8" opacity="0.45"/>',
            f'<path d="{path(main_right, view, padding, svg_scale, close=True)}" fill="none" stroke="#cbd5e1" stroke-width="0.8" opacity="0.45"/>',
            f'<path d="{corridor(pit_left, pit_right, view, padding, svg_scale)}" fill="#facc15" opacity="0.18" stroke="#facc15" stroke-width="1.1"/>',
            f'<path d="{path(pit_center, view, padding, svg_scale)}" fill="none" stroke="#fde047" stroke-width="2.2"/>',
            f'<path d="{path([main_center[index] for index in suspect_indices], view, padding, svg_scale)}" fill="none" stroke="#ef4444" stroke-width="5.0" opacity="0.84"/>',
            svg_marker("pitManualEnd", pit_exit, view, padding, svg_scale, "#38bdf8"),
            svg_marker("nearest main", nearest_main["point"], view, padding, svg_scale, "#f472b6"),
            svg_marker("direction-compatible merge", merge["point"], view, padding, svg_scale, "#22c55e"),
            svg_text(f"false chicane indices {suspect_start}-{suspect_end}", 24, 54, 12, "#fecaca"),
            svg_text(f"width variation in 80m zone {analysis['widthVariationInZone']:.2f}m", 24, 72, 12, "#e2e8f0"),
            svg_text(f"max curvature spike {analysis['maxCurvatureSpike']:.4f}", 24, 90, 12, "#e2e8f0"),
            svg_text(f"nearest pit exit distance {analysis['nearestPitExitDistance']:.2f}m", 24, 108, 12, "#e2e8f0"),
        ]
    )
    write_svg(DEBUG_DIR / "interlagos_pit_exit_core_problem_analysis.svg", lines)

    _, _, svg_scale, padding, lines = svg_canvas(view, "Interlagos MainTrack Pit Exit Zone Candidate")
    lines.extend(
        [
            f'<path d="{corridor(main_left, main_right, view, padding, svg_scale)}" fill="#64748b" opacity="0.10"/>',
            f'<path d="{path(main_center, view, padding, svg_scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1" opacity="0.45"/>',
            f'<path d="{path(original_segment, view, padding, svg_scale)}" fill="none" stroke="#ef4444" stroke-width="5.0" opacity="0.86"/>',
            f'<path d="{path(candidate_segment, view, padding, svg_scale)}" fill="none" stroke="#22d3ee" stroke-width="4.0" opacity="0.95"/>',
            f'<path d="{corridor(pit_left, pit_right, view, padding, svg_scale)}" fill="#facc15" opacity="0.15" stroke="#facc15" stroke-width="1.0"/>',
            f'<path d="{path(pit_center, view, padding, svg_scale)}" fill="none" stroke="#fde047" stroke-width="2.2"/>',
            svg_marker("anchor start", main_center[anchor_start], view, padding, svg_scale, "#38bdf8"),
            svg_marker("anchor end", main_center[anchor_end], view, padding, svg_scale, "#38bdf8"),
            svg_text("red=current local MainTrack segment", 24, 54, 12, "#fecaca"),
            svg_text("cyan=debug-only smoothed candidate", 24, 72, 12, "#a5f3fc"),
            svg_text(f"max candidate displacement {max_displacement:.2f}m", 24, 90, 12, "#e2e8f0"),
        ]
    )
    write_svg(DEBUG_DIR / "interlagos_maintrack_pit_exit_zone_candidate.svg", lines)

    _, _, svg_scale, padding, lines = svg_canvas(view, "Interlagos Pit Exit Transition Geometry")
    lines.extend(
        [
            f'<path d="{corridor(main_left, main_right, view, padding, svg_scale)}" fill="#64748b" opacity="0.10"/>',
            f'<path d="{path(main_center, view, padding, svg_scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.0" opacity="0.45"/>',
            f'<path d="{path(candidate_segment, view, padding, svg_scale)}" fill="none" stroke="#22d3ee" stroke-width="3.0" opacity="0.7"/>',
            f'<path d="{corridor(pit_left, pit_right, view, padding, svg_scale)}" fill="#facc15" opacity="0.16" stroke="#facc15" stroke-width="1.0"/>',
            f'<path d="{path(pit_center, view, padding, svg_scale)}" fill="none" stroke="#fde047" stroke-width="2.2"/>',
            f'<path d="{path(transition_center, view, padding, svg_scale)}" fill="none" stroke="#fb923c" stroke-width="4.0" stroke-dasharray="10 7"/>',
            svg_marker("pit exit start", transition_start, view, padding, svg_scale, "#38bdf8"),
            svg_marker("main merge end", transition_end, view, padding, svg_scale, "#22c55e"),
            svg_text(f"transition length {transition['length']:.2f}m", 24, 54, 12, "#fed7aa"),
            svg_text(f"merge distance {merge['distance']:.2f}m, direction diff {merge['directionDiffDeg']:.1f}deg", 24, 72, 12, "#fed7aa"),
        ]
    )
    write_svg(DEBUG_DIR / "interlagos_pit_exit_transition_geometry.svg", lines)

    print(DEBUG_DIR / "interlagos_pit_exit_core_problem_analysis.json")
    print(DEBUG_DIR / "interlagos_maintrack_pit_exit_zone_candidate.json")
    print(DEBUG_DIR / "interlagos_pit_exit_transition_geometry.json")


if __name__ == "__main__":
    build()
