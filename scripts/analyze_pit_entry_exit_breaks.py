"""Export debug-only pit entry/exit break analysis and local candidates.

This script reads current debug/cache artifacts and writes new debug artifacts
under data/debug. It does not mutate authoritative geometry, runtime geometry,
projection, map-space, lateral offset, or pitlane geometry.
"""
from __future__ import annotations

import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"
MAIN_TRACK_CACHE = REPO_ROOT / "data" / "cache" / "tracks" / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
MANUAL_TRIM_JSON = DEBUG_DIR / "interlagos_pitlane_trimmed_manual_05_05.json"
PITLANE_SURFACE_JSON = DEBUG_DIR / "interlagos_pitlane_surface_derived_geometry.json"
PITLANE_SURFACE_BOUNDARY_JSON = DEBUG_DIR / "interlagos_pitlane_surface_boundary.json"
MANUAL_TRIM_REPORT_JSON = DEBUG_DIR / "interlagos_pitlane_manual_trim_final_report.json"
ENTRY_EXIT_ZONE_ANALYSIS_JSON = DEBUG_DIR / "interlagos_pitlane_entry_exit_zone_analysis.json"
PIT_EXIT_CORE_ANALYSIS_JSON = DEBUG_DIR / "interlagos_pit_exit_core_problem_analysis.json"

COMBINED_ANALYSIS_JSON = DEBUG_DIR / "interlagos_pit_entry_exit_breaks_combined_analysis.json"
COMBINED_ANALYSIS_SVG = DEBUG_DIR / "interlagos_pit_entry_exit_breaks_combined_analysis.svg"
ENTRY_CANDIDATE_JSON = DEBUG_DIR / "interlagos_maintrack_entry_zone_candidate.json"
ENTRY_CANDIDATE_SVG = DEBUG_DIR / "interlagos_maintrack_entry_zone_candidate.svg"
EXIT_CANDIDATE_JSON = DEBUG_DIR / "interlagos_maintrack_exit_zone_candidate_v2.json"
EXIT_CANDIDATE_SVG = DEBUG_DIR / "interlagos_maintrack_exit_zone_candidate_v2.svg"
ENTRY_TRANSITION_JSON = DEBUG_DIR / "interlagos_pit_entry_transition_candidates.json"
ENTRY_TRANSITION_SVG = DEBUG_DIR / "interlagos_pit_entry_transition_candidates.svg"
EXIT_TRANSITION_JSON = DEBUG_DIR / "interlagos_pit_exit_transition_candidates_v2.json"
EXIT_TRANSITION_SVG = DEBUG_DIR / "interlagos_pit_exit_transition_candidates_v2.svg"
FINAL_REPORT_JSON = DEBUG_DIR / "interlagos_pit_entry_exit_breaks_final_report.json"

PIT_MANUAL_START = {"x": -339.274471, "y": -425.069001}
PIT_MANUAL_END = {"x": -432.446484, "y": -75.929951}
ZONE_RADIUS_METERS = 100.0
SUSPECT_PROXIMITY_METERS = 12.0
EXCESSIVE_PROXIMITY_METERS = 8.0
CURVATURE_SPIKE_FLOOR = 0.035
HEADING_CHANGE_ABNORMAL_DEG = 85.0
WIDTH_VARIATION_ABNORMAL_METERS = 4.0
MAX_ALLOWED_CORRECTION_DISPLACEMENT = 45.0

Point = Dict[str, float]


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def optional_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"_missing": True, "_path": str(path)}
    return read_json(path)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def point_xy(point: Dict[str, Any]) -> Point:
    return {"x": float(point["x"]), "y": float(point.get("y", point.get("z", 0.0)))}


def points_xy(points: Iterable[Dict[str, Any]]) -> List[Point]:
    return [point_xy(point) for point in points or []]


def point_round(point: Point, digits: int = 6) -> Point:
    return {"x": round(float(point["x"]), digits), "y": round(float(point["y"]), digits)}


def points_round(points: Iterable[Point], digits: int = 6) -> List[Point]:
    return [point_round(point, digits) for point in points]


def distance(a: Point, b: Point) -> float:
    return math.hypot(b["x"] - a["x"], b["y"] - a["y"])


def subtract(a: Point, b: Point) -> Point:
    return {"x": a["x"] - b["x"], "y": a["y"] - b["y"]}


def add(a: Point, b: Point) -> Point:
    return {"x": a["x"] + b["x"], "y": a["y"] + b["y"]}


def scale_vector(v: Point, factor: float) -> Point:
    return {"x": v["x"] * factor, "y": v["y"] * factor}


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


def heading_at(points: List[Point], index: int, span: int = 3) -> float:
    return heading(points[max(0, index - span)], points[min(len(points) - 1, index + span)])


def tangent(points: List[Point], index: int, span: int = 5) -> Point:
    start = points[max(0, index - span)]
    end = points[min(len(points) - 1, index + span)]
    return normalize(subtract(end, start))


def tangent_backward(points: List[Point], index: int, span: int = 14) -> Point:
    return normalize(subtract(points[index], points[max(0, index - span)]))


def tangent_forward(points: List[Point], index: int, span: int = 14) -> Point:
    return normalize(subtract(points[min(len(points) - 1, index + span)], points[index]))


def signed_curvature(points: List[Point], index: int, closed: bool = True) -> float:
    count = len(points)
    if count < 3:
        return 0.0
    if closed:
        a = points[(index - 1) % count]
        b = points[index]
        c = points[(index + 1) % count]
    else:
        if index <= 0 or index >= count - 1:
            return 0.0
        a = points[index - 1]
        b = points[index]
        c = points[index + 1]
    v1 = subtract(b, a)
    v2 = subtract(c, b)
    turn = math.atan2(cross(v1, v2), dot(v1, v2))
    ds = max((distance(a, b) + distance(b, c)) / 2.0, 1e-6)
    return turn / ds


def max_abs_curvature(points: List[Point], closed: bool = False) -> float:
    if len(points) < 3:
        return 0.0
    indices = range(len(points)) if closed else range(1, len(points) - 1)
    return max(abs(signed_curvature(points, index, closed=closed)) for index in indices)


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
    if best is None:
        return {"index": 0, "t": 0.0, "point": point_round(line[0]), "distance": distance(point, line[0])}
    best["point"] = point_round(best["point"])
    best["distance"] = round(float(best["distance"]), 6)
    return best


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


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * p))))
    return float(ordered[pos])


def polyline_length(points: List[Point]) -> float:
    return sum(distance(points[index - 1], points[index]) for index in range(1, len(points)))


def cubic_hermite(a: Point, b: Point, tangent_a: Point, tangent_b: Point, count: int, tension: float = 0.55) -> List[Point]:
    chord = distance(a, b)
    m0 = scale_vector(tangent_a, chord * tension)
    m1 = scale_vector(tangent_b, chord * tension)
    out: List[Point] = []
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


def bezier(p0: Point, p1: Point, p2: Point, p3: Point, count: int = 36) -> List[Point]:
    out: List[Point] = []
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


def maybe_limit_displacement(original: List[Point], candidate: List[Point], max_allowed: float) -> List[Point]:
    limited: List[Point] = []
    for original_point, candidate_point in zip(original, candidate):
        delta = subtract(candidate_point, original_point)
        correction = math.hypot(delta["x"], delta["y"])
        if correction <= max_allowed:
            limited.append(candidate_point)
            continue
        factor = max_allowed / correction
        limited.append(add(original_point, scale_vector(delta, factor)))
    return limited


def width_stats(widths: List[float], indices: List[int]) -> Dict[str, float]:
    values = [widths[index] for index in indices if 0 <= index < len(widths)]
    if not values:
        return {"min": 0.0, "avg": 0.0, "max": 0.0, "variation": 0.0}
    return {
        "min": round(min(values), 6),
        "avg": round(mean(values), 6),
        "max": round(max(values), 6),
        "variation": round(max(values) - min(values), 6),
    }


def run_heading_change(headings: List[float], indices: List[int]) -> float:
    total = 0.0
    previous: Optional[int] = None
    for index in indices:
        if previous is not None and index == previous + 1:
            total += angle_diff(headings[previous], headings[index])
        previous = index
    return math.degrees(total)


def run_report(
    run: List[int],
    zone_center: Point,
    main_center: List[Point],
    main_width: List[float],
    pit_center: List[Point],
    curvatures: List[float],
    headings: List[float],
    curvature_spike_threshold: float,
) -> Dict[str, Any]:
    distances_to_zone = [distance(main_center[index], zone_center) for index in run]
    nearest_pit = [nearest_polyline(main_center[index], pit_center) for index in run]
    widths = width_stats(main_width, run)
    signs = []
    for index in run[1:-1]:
        curv = curvatures[index]
        signs.append(1 if curv > 0.001 else -1 if curv < -0.001 else 0)
    sign_changes = sum(1 for index in range(1, len(signs)) if signs[index] and signs[index - 1] and signs[index] != signs[index - 1])
    max_spike_index = max(run, key=lambda item: abs(curvatures[item]))
    min_pit_item = min(nearest_pit, key=lambda item: item["distance"])
    return {
        "startIndex": run[0],
        "endIndex": run[-1],
        "pointCount": len(run),
        "minDistanceToZoneCenter": round(min(distances_to_zone), 6),
        "maxDistanceToZoneCenter": round(max(distances_to_zone), 6),
        "minDistanceToPitLane": round(min(item["distance"] for item in nearest_pit), 6),
        "avgDistanceToPitLane": round(mean(item["distance"] for item in nearest_pit), 6),
        "nearestPitPoint": min_pit_item,
        "maxAbsCurvature": round(max(abs(curvatures[index]) for index in run), 8),
        "maxCurvatureIndex": max_spike_index,
        "avgAbsCurvature": round(mean(abs(curvatures[index]) for index in run), 8),
        "headingChangeDeg": round(run_heading_change(headings, run), 6),
        "widthMin": widths["min"],
        "widthAvg": widths["avg"],
        "widthMax": widths["max"],
        "widthVariation": widths["variation"],
        "curvatureSignChanges": sign_changes,
        "curvatureSpikeDetected": max(abs(curvatures[index]) for index in run) >= curvature_spike_threshold,
        "headingChangeAbnormal": run_heading_change(headings, run) >= HEADING_CHANGE_ABNORMAL_DEG,
        "widthVariationAbnormal": widths["variation"] >= WIDTH_VARIATION_ABNORMAL_METERS,
        "excessivePitLaneProximity": min(item["distance"] for item in nearest_pit) <= EXCESSIVE_PROXIMITY_METERS,
    }


def suspicion_reason(zone_label: str, report: Dict[str, Any]) -> str:
    reasons = []
    if report["curvatureSpikeDetected"]:
        reasons.append(f"curvature spike {report['maxAbsCurvature']:.4f}")
    if report["headingChangeAbnormal"]:
        reasons.append(f"heading change {report['headingChangeDeg']:.1f} deg")
    if report["widthVariationAbnormal"]:
        reasons.append(f"width variation {report['widthVariation']:.2f} m")
    if report["excessivePitLaneProximity"]:
        reasons.append(f"pitlane proximity {report['minDistanceToPitLane']:.2f} m")
    if not reasons:
        reasons.append("largest local anomaly inside pit transition window")
    return f"{zone_label} suspected MainTrack break: " + "; ".join(reasons)


def analyze_zone(
    zone_id: str,
    zone_label: str,
    zone_center: Point,
    radius: float,
    main_center: List[Point],
    main_width: List[float],
    pit_center: List[Point],
    curvatures: List[float],
    headings: List[float],
    curvature_spike_threshold: float,
) -> Dict[str, Any]:
    spatial_indices = [index for index, point in enumerate(main_center) if distance(point, zone_center) <= radius]
    runs = contiguous_runs(spatial_indices)
    reports = [
        run_report(run, zone_center, main_center, main_width, pit_center, curvatures, headings, curvature_spike_threshold)
        for run in runs
    ]
    if not reports:
        raise RuntimeError(f"No MainTrackGeometry points found in {zone_id} zone")

    def score(report: Dict[str, Any]) -> float:
        curvature_score = report["maxAbsCurvature"] / max(curvature_spike_threshold, 1e-9)
        heading_score = report["headingChangeDeg"] / HEADING_CHANGE_ABNORMAL_DEG
        width_score = report["widthVariation"] / WIDTH_VARIATION_ABNORMAL_METERS
        proximity_score = max(0.0, (25.0 - report["minDistanceToPitLane"]) / 25.0)
        center_score = max(0.0, (radius - report["minDistanceToZoneCenter"]) / radius)
        return 2.4 * curvature_score + 1.4 * heading_score + width_score + 3.2 * proximity_score + center_score

    selected_report = max(reports, key=score)
    selected_run = list(range(selected_report["startIndex"], selected_report["endIndex"] + 1))
    hot_indices = [
        index
        for index in selected_run
        if abs(curvatures[index]) >= curvature_spike_threshold
        or nearest_polyline(main_center[index], pit_center)["distance"] <= SUSPECT_PROXIMITY_METERS
    ]
    if not hot_indices:
        top_index = int(selected_report["maxCurvatureIndex"])
        hot_indices = [top_index]

    suspect_start = max(selected_run[0], min(hot_indices) - 6)
    suspect_end = min(selected_run[-1], max(hot_indices) + 6)
    suspect_indices = list(range(suspect_start, suspect_end + 1))
    suspect_width = width_stats(main_width, suspect_indices)
    suspect_nearest = [nearest_polyline(main_center[index], pit_center) for index in suspect_indices]
    nearest_pit = min(suspect_nearest, key=lambda item: item["distance"])
    max_curv_index = max(suspect_indices, key=lambda index: abs(curvatures[index]))
    zone_width = width_stats(main_width, spatial_indices)
    samples = []
    for index in spatial_indices:
        nearest_pit_item = nearest_polyline(main_center[index], pit_center)
        samples.append(
            {
                "index": index,
                "point": point_round(main_center[index]),
                "distanceToZoneCenter": round(distance(main_center[index], zone_center), 6),
                "distanceToPitLane": nearest_pit_item["distance"],
                "nearestPitPoint": nearest_pit_item,
                "curvature": round(curvatures[index], 8),
                "absCurvature": round(abs(curvatures[index]), 8),
                "headingDeg": round(math.degrees(headings[index]), 6),
                "width": round(main_width[index], 6),
                "suspected": suspect_start <= index <= suspect_end,
            }
        )

    return {
        "zoneId": zone_id,
        "center": point_round(zone_center),
        "radiusMeters": radius,
        "mainTrackPointsInsideRadius": samples,
        "spatialRuns": reports,
        "suspectedStartIndex": suspect_start,
        "suspectedEndIndex": suspect_end,
        "suspectedIndices": suspect_indices,
        "suspectedPointCount": len(suspect_indices),
        "maxCurvatureSpike": round(abs(curvatures[max_curv_index]), 8),
        "maxCurvatureSpikeIndex": max_curv_index,
        "headingChangeDeg": round(run_heading_change(headings, suspect_indices), 6),
        "widthVariation": suspect_width["variation"],
        "widthMin": suspect_width["min"],
        "widthAvg": suspect_width["avg"],
        "widthMax": suspect_width["max"],
        "zoneWidthVariation": zone_width["variation"],
        "minDistanceToPitLane": nearest_pit["distance"],
        "nearestPitPoint": nearest_pit,
        "reason": suspicion_reason(zone_label, selected_report),
        "abnormalSignals": {
            "curvatureSpike": abs(curvatures[max_curv_index]) >= curvature_spike_threshold,
            "headingChange": run_heading_change(headings, suspect_indices) >= HEADING_CHANGE_ABNORMAL_DEG,
            "widthVariation": suspect_width["variation"] >= WIDTH_VARIATION_ABNORMAL_METERS,
            "excessivePitLaneProximity": nearest_pit["distance"] <= EXCESSIVE_PROXIMITY_METERS,
        },
    }


def build_maintrack_candidate(
    zone_id: str,
    source_name: str,
    analysis: Dict[str, Any],
    main_center: List[Point],
    main_width: List[float],
    pit_center: List[Point],
    output_json: Path,
    output_svg: Path,
) -> Dict[str, Any]:
    suspect_start = int(analysis["suspectedStartIndex"])
    suspect_end = int(analysis["suspectedEndIndex"])
    anchor_start = max(0, suspect_start - 10)
    anchor_end = min(len(main_center) - 1, suspect_end + 10)
    original_segment = main_center[anchor_start : anchor_end + 1]
    candidate_segment = cubic_hermite(
        main_center[anchor_start],
        main_center[anchor_end],
        tangent_backward(main_center, anchor_start, span=16),
        tangent_forward(main_center, anchor_end, span=16),
        len(original_segment),
    )
    candidate_segment = maybe_limit_displacement(original_segment, candidate_segment, MAX_ALLOWED_CORRECTION_DISPLACEMENT)
    corrections = [distance(original, candidate) for original, candidate in zip(original_segment, candidate_segment)]
    before_indices = list(range(max(0, anchor_start - 12), anchor_start + 1))
    after_indices = list(range(anchor_end, min(len(main_width) - 1, anchor_end + 12) + 1))
    payload = {
        "generatedAt": now_iso(),
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "name": "MainTrackEntryZoneCandidate" if zone_id == "entryZone" else "MainTrackExitZoneCandidate",
        "source": source_name,
        "method": "debug_local_cubic_hermite_between_existing_maintrack_anchors",
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "mainTrackGeometryChanged": False,
        "trackPhysicsGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "pitLaneGeometryChanged": False,
        "readyForRuntimeIntegration": False,
        "selectedAutomatically": False,
        "suspectedStartIndex": suspect_start,
        "suspectedEndIndex": suspect_end,
        "suspectedIndices": analysis["suspectedIndices"],
        "anchorStartIndex": anchor_start,
        "anchorEndIndex": anchor_end,
        "originalSegment": points_round(original_segment),
        "candidateSegment": points_round(candidate_segment),
        "maxCorrectionDisplacement": round(max(corrections), 6),
        "avgCorrectionDisplacement": round(mean(corrections), 6),
        "maxAllowedCorrectionDisplacement": MAX_ALLOWED_CORRECTION_DISPLACEMENT,
        "widthBefore": width_stats(main_width, before_indices),
        "widthAfter": width_stats(main_width, after_indices),
    }
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_candidate_svg(
        output_svg,
        "MainTrack entry local candidate" if zone_id == "entryZone" else "MainTrack exit local candidate",
        main_center,
        original_segment,
        candidate_segment,
        pit_center,
        main_center[anchor_start],
        main_center[anchor_end],
        analysis,
    )
    return payload


def transition_tangent_start(points: List[Point]) -> Point:
    if len(points) < 2:
        return {"x": 0.0, "y": 0.0}
    return normalize(subtract(points[1], points[0]))


def transition_tangent_end(points: List[Point]) -> Point:
    if len(points) < 2:
        return {"x": 0.0, "y": 0.0}
    return normalize(subtract(points[-1], points[-2]))


def spaced_take(sorted_candidates: List[Dict[str, Any]], count: int, min_index_gap: int = 8) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for candidate in sorted_candidates:
        if all(abs(candidate["mainTrackIndex"] - item["mainTrackIndex"]) >= min_index_gap for item in selected):
            selected.append(candidate)
        if len(selected) >= count:
            break
    return selected


def build_transition_candidate(
    transition_id: str,
    main_index: int,
    start_point: Point,
    end_point: Point,
    start_reference_tangent: Point,
    end_reference_tangent: Point,
    start_control_tangent: Point,
    end_control_tangent: Point,
    score_base: float,
    score_reason: str,
) -> Dict[str, Any]:
    straight_distance = distance(start_point, end_point)
    p1 = add(start_point, scale_vector(normalize(start_control_tangent), straight_distance * 0.42))
    p2 = add(end_point, scale_vector(normalize(end_control_tangent), -straight_distance * 0.42))
    centerline = bezier(start_point, p1, p2, end_point, 38)
    start_diff = angle_between(start_reference_tangent, transition_tangent_start(centerline))
    end_diff = angle_between(end_reference_tangent, transition_tangent_end(centerline))
    curvature = max_abs_curvature(centerline, closed=False)
    score = score_base + start_diff * 0.75 + end_diff * 0.75 + curvature * 90.0 + straight_distance * 0.04
    return {
        "id": transition_id,
        "mainTrackIndex": main_index,
        "startPoint": point_round(start_point),
        "endPoint": point_round(end_point),
        "controlPoints": points_round([start_point, p1, p2, end_point]),
        "centerline": points_round(centerline),
        "length": round(polyline_length(centerline), 6),
        "maxCurvature": round(curvature, 8),
        "directionDiffAtStart": round(start_diff, 6),
        "directionDiffAtEnd": round(end_diff, 6),
        "distanceToMain": round(straight_distance, 6),
        "source": "debug_bezier_fallback",
        "score": round(score, 6),
        "scoreReason": score_reason,
        "selectedAutomatically": False,
    }


def build_entry_transition_candidates(
    analysis: Dict[str, Any],
    main_center: List[Point],
    pit_center: List[Point],
    curvatures: List[float],
) -> Dict[str, Any]:
    pit_start = pit_center[0]
    pit_start_tangent = tangent(pit_center, 0, span=8)
    suspect_indices = set(analysis["suspectedIndices"])
    pool = []
    for sample in analysis["mainTrackPointsInsideRadius"]:
        index = int(sample["index"])
        if index in suspect_indices:
            continue
        point = main_center[index]
        main_tangent = tangent(main_center, index, span=8)
        direction_to_pit = normalize(subtract(pit_start, point))
        start_diff_hint = angle_between(main_tangent, direction_to_pit)
        pit_proximity_penalty = max(0.0, 16.0 - float(sample["distanceToPitLane"])) * 2.0
        target_distance_penalty = abs(distance(point, pit_start) - 55.0) * 0.35
        score = start_diff_hint * 0.8 + target_distance_penalty + pit_proximity_penalty + abs(curvatures[index]) * 60.0
        pool.append(
            {
                "mainTrackIndex": index,
                "score": score,
                "scoreReason": "entry candidates exclude suspected absorbed segment and prefer stable MainTrack anchors",
            }
        )
    selected = spaced_take(sorted(pool, key=lambda item: item["score"]), 5, min_index_gap=9)
    candidates = []
    for rank, item in enumerate(selected, start=1):
        index = item["mainTrackIndex"]
        main_point = main_center[index]
        main_tangent = tangent(main_center, index, span=8)
        candidates.append(
            build_transition_candidate(
                f"entry_transition_candidate_{rank:02d}",
                index,
                main_point,
                pit_start,
                main_tangent,
                pit_start_tangent,
                main_tangent,
                pit_start_tangent,
                item["score"],
                item["scoreReason"],
            )
        )
    payload = {
        "generatedAt": now_iso(),
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "name": "PitEntryTransitionGeometry",
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "mainTrackGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "readyForRuntimeIntegration": False,
        "selectedAutomatically": False,
        "description": "Separate debug branch candidates from MainTrackGeometry to pitManualStart; no candidate is promoted.",
        "pitManualStart": point_round(pit_start),
        "candidateCount": len(candidates),
        "candidates": candidates,
    }
    ENTRY_TRANSITION_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_transition_svg(ENTRY_TRANSITION_SVG, "PitEntryTransitionGeometry candidates", main_center, pit_center, candidates, "entry")
    return payload


def build_exit_transition_candidates(
    analysis: Dict[str, Any],
    main_center: List[Point],
    pit_center: List[Point],
    curvatures: List[float],
) -> Dict[str, Any]:
    pit_end = pit_center[-1]
    pit_end_tangent = tangent(pit_center, len(pit_center) - 1, span=8)
    suspect_indices = set(analysis["suspectedIndices"])
    samples = analysis["mainTrackPointsInsideRadius"]
    nearest_sample = min(samples, key=lambda sample: distance(main_center[int(sample["index"])], pit_end))
    pool = []
    for sample in samples:
        index = int(sample["index"])
        point = main_center[index]
        main_tangent = tangent(main_center, index, span=8)
        direction_diff = angle_between(pit_end_tangent, main_tangent)
        suspected_penalty = 55.0 if index in suspect_indices else 0.0
        pit_proximity_penalty = max(0.0, 12.0 - float(sample["distanceToPitLane"])) * 1.6
        distance_penalty = abs(distance(point, pit_end) - 58.0) * 0.25
        score = direction_diff * 1.1 + suspected_penalty + pit_proximity_penalty + distance_penalty + abs(curvatures[index]) * 50.0
        pool.append(
            {
                "mainTrackIndex": index,
                "score": score,
                "scoreReason": "exit candidates rank direction compatibility and do not auto-accept nearest point",
            }
        )
    selected = spaced_take(sorted(pool, key=lambda item: item["score"]), 6, min_index_gap=9)
    if all(item["mainTrackIndex"] != int(nearest_sample["index"]) for item in selected):
        selected.append(
            {
                "mainTrackIndex": int(nearest_sample["index"]),
                "score": 9999.0,
                "scoreReason": "nearest point included for comparison only; not automatically accepted",
            }
        )
    candidates = []
    for rank, item in enumerate(selected, start=1):
        index = item["mainTrackIndex"]
        main_point = main_center[index]
        main_tangent = tangent(main_center, index, span=8)
        candidates.append(
            build_transition_candidate(
                f"exit_transition_candidate_{rank:02d}",
                index,
                pit_end,
                main_point,
                pit_end_tangent,
                main_tangent,
                pit_end_tangent,
                main_tangent,
                item["score"],
                item["scoreReason"],
            )
        )
    payload = {
        "generatedAt": now_iso(),
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "name": "PitExitTransitionGeometry",
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "mainTrackGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "readyForRuntimeIntegration": False,
        "selectedAutomatically": False,
        "description": "Separate debug branch candidates from pitManualEnd to MainTrackGeometry; no merge point is selected automatically.",
        "pitManualEnd": point_round(pit_end),
        "candidateCount": len(candidates),
        "candidates": candidates,
    }
    EXIT_TRANSITION_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_transition_svg(EXIT_TRANSITION_SVG, "PitExitTransitionGeometry candidates", main_center, pit_center, candidates, "exit")
    return payload


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


def svg_path(points: List[Point], view: Dict[str, float], padding: float, scale: float, close: bool = False) -> str:
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


def svg_text(text: str, x: float, y: float, size: int = 11, color: str = "#e5e7eb") -> str:
    return f'<text x="{x:.2f}" y="{y:.2f}" fill="{color}" font-size="{size}" font-family="Consolas, monospace">{html.escape(text)}</text>'


def svg_marker(label: str, point: Point, view: Dict[str, float], padding: float, scale: float, color: str, radius: float = 5.0) -> str:
    x, y = map_to_svg(point, view, padding, scale)
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.1f}" fill="{color}" stroke="#020617" stroke-width="2"/>'
        + svg_text(label, x + 8, y - 8, 10, color)
    )


def svg_canvas(view: Dict[str, float], title: str, max_width: int = 1320, max_height: int = 940) -> Tuple[int, int, float, int, List[str]]:
    padding = 48
    scale = min((max_width - padding * 2) / max(view["width"], 1.0), (max_height - padding * 2) / max(view["height"], 1.0))
    width = int(view["width"] * scale + padding * 2)
    height = int(view["height"] * scale + padding * 2)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#050816"/>',
        svg_text(title, 22, 30, 16, "#f8fafc"),
        svg_text("debug-only: runtimeChanged=false, no authoritative geometry changed", 22, height - 18, 10, "#94a3b8"),
    ]
    return width, height, scale, padding, lines


def write_svg(path: Path, lines: List[str]) -> None:
    path.write_text("\n".join([*lines, "</svg>"]), encoding="utf-8")


def write_combined_svg(main_center: List[Point], pit_center: List[Point], entry: Dict[str, Any], exit_: Dict[str, Any]) -> None:
    view = bounds([*main_center, *pit_center, PIT_MANUAL_START, PIT_MANUAL_END], margin=70.0)
    _, _, svg_scale, padding, lines = svg_canvas(view, "Interlagos pit entry/exit MainTrack break analysis")
    entry_x, entry_y = map_to_svg(PIT_MANUAL_START, view, padding, svg_scale)
    exit_x, exit_y = map_to_svg(PIT_MANUAL_END, view, padding, svg_scale)
    lines.extend(
        [
            f'<path d="{svg_path(main_center, view, padding, svg_scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.25" opacity="0.72"/>',
            f'<path d="{svg_path(pit_center, view, padding, svg_scale)}" fill="none" stroke="#fde047" stroke-width="2.8" opacity="0.95"/>',
            f'<circle cx="{entry_x:.2f}" cy="{entry_y:.2f}" r="{ZONE_RADIUS_METERS * svg_scale:.2f}" fill="#22c55e" opacity="0.12" stroke="#22c55e" stroke-width="1.2"/>',
            f'<circle cx="{exit_x:.2f}" cy="{exit_y:.2f}" r="{ZONE_RADIUS_METERS * svg_scale:.2f}" fill="#ef4444" opacity="0.12" stroke="#ef4444" stroke-width="1.2"/>',
            f'<path d="{svg_path([main_center[index] for index in entry["suspectedIndices"]], view, padding, svg_scale)}" fill="none" stroke="#fb923c" stroke-width="5.0" opacity="0.96"/>',
            f'<path d="{svg_path([main_center[index] for index in exit_["suspectedIndices"]], view, padding, svg_scale)}" fill="none" stroke="#ef4444" stroke-width="5.0" opacity="0.96"/>',
            svg_marker("PIT ENTRY", PIT_MANUAL_START, view, padding, svg_scale, "#22c55e", radius=6.5),
            svg_marker("PIT EXIT", PIT_MANUAL_END, view, padding, svg_scale, "#ef4444", radius=6.5),
            svg_text(f"entry suspected {entry['suspectedStartIndex']}-{entry['suspectedEndIndex']}", 24, 56, 12, "#fed7aa"),
            svg_text(f"exit suspected {exit_['suspectedStartIndex']}-{exit_['suspectedEndIndex']}", 24, 74, 12, "#fecaca"),
            svg_text("gray=MainTrackGeometry, yellow=PitLaneGeometryTrimmedManual 05_05", 24, 92, 12, "#e2e8f0"),
        ]
    )
    for zone, color in ((entry, "#fb923c"), (exit_, "#ef4444")):
        indices = zone["suspectedIndices"]
        step = max(1, len(indices) // 8)
        for index in indices[::step]:
            lines.append(svg_marker(str(index), main_center[index], view, padding, svg_scale, color, radius=3.2))
    write_svg(COMBINED_ANALYSIS_SVG, lines)


def write_candidate_svg(
    output: Path,
    title: str,
    main_center: List[Point],
    original_segment: List[Point],
    candidate_segment: List[Point],
    pit_center: List[Point],
    anchor_start: Point,
    anchor_end: Point,
    analysis: Dict[str, Any],
) -> None:
    local_points = [*original_segment, *candidate_segment, *pit_center, anchor_start, anchor_end]
    view = bounds(local_points, margin=34.0)
    _, _, svg_scale, padding, lines = svg_canvas(view, title)
    lines.extend(
        [
            f'<path d="{svg_path(main_center, view, padding, svg_scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.1" opacity="0.45"/>',
            f'<path d="{svg_path(pit_center, view, padding, svg_scale)}" fill="none" stroke="#fde047" stroke-width="2.4" opacity="0.92"/>',
            f'<path d="{svg_path(original_segment, view, padding, svg_scale)}" fill="none" stroke="#ef4444" stroke-width="5.2" opacity="0.88"/>',
            f'<path d="{svg_path(candidate_segment, view, padding, svg_scale)}" fill="none" stroke="#22d3ee" stroke-width="4.0" opacity="0.96"/>',
            svg_marker("anchor start", anchor_start, view, padding, svg_scale, "#38bdf8", radius=5.6),
            svg_marker("anchor end", anchor_end, view, padding, svg_scale, "#38bdf8", radius=5.6),
            svg_text("red=original problem segment, cyan=debug candidate, yellow=pitlane", 24, 56, 12, "#e2e8f0"),
            svg_text(f"suspected {analysis['suspectedStartIndex']}-{analysis['suspectedEndIndex']}", 24, 74, 12, "#fecaca"),
        ]
    )
    for index in analysis["suspectedIndices"][:: max(1, len(analysis["suspectedIndices"]) // 7)]:
        lines.append(svg_marker(str(index), main_center[index], view, padding, svg_scale, "#fb7185", radius=3.2))
    write_svg(output, lines)


def write_transition_svg(output: Path, title: str, main_center: List[Point], pit_center: List[Point], candidates: List[Dict[str, Any]], mode: str) -> None:
    candidate_points = []
    for candidate in candidates:
        candidate_points.extend(candidate["centerline"])
        candidate_points.append(candidate["startPoint"])
        candidate_points.append(candidate["endPoint"])
    view = bounds([*candidate_points, *pit_center], margin=38.0)
    _, _, svg_scale, padding, lines = svg_canvas(view, title)
    branch_color = "#22c55e" if mode == "entry" else "#fb923c"
    label_prefix = "entry" if mode == "entry" else "exit"
    lines.extend(
        [
            f'<path d="{svg_path(main_center, view, padding, svg_scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.1" opacity="0.45"/>',
            f'<path d="{svg_path(pit_center, view, padding, svg_scale)}" fill="none" stroke="#fde047" stroke-width="2.6" opacity="0.94"/>',
            svg_text("dashed branches are debug-only PitTransitionGeometry candidates", 24, 56, 12, "#e2e8f0"),
            svg_text("no candidate selected automatically", 24, 74, 12, "#f8fafc"),
        ]
    )
    for candidate in candidates:
        centerline = candidate["centerline"]
        width = 3.4 if "9999" not in str(candidate.get("score", "")) else 2.4
        lines.append(
            f'<path d="{svg_path(centerline, view, padding, svg_scale)}" fill="none" stroke="{branch_color}" stroke-width="{width:.1f}" stroke-dasharray="10 7" opacity="0.86"/>'
        )
        endpoint = candidate["endPoint"] if mode == "exit" else candidate["startPoint"]
        label = f"{candidate['mainTrackIndex']} d={candidate['distanceToMain']:.1f}m a={candidate['directionDiffAtEnd' if mode == 'exit' else 'directionDiffAtStart']:.0f}"
        lines.append(svg_marker(label, endpoint, view, padding, svg_scale, branch_color, radius=4.2))
    manual_label = "PIT ENTRY" if mode == "entry" else "PIT EXIT"
    manual_point = pit_center[0] if mode == "entry" else pit_center[-1]
    lines.append(svg_marker(manual_label, manual_point, view, padding, svg_scale, "#fde047", radius=6.2))
    lines.append(svg_text(f"{label_prefix} candidates={len(candidates)}", 24, 92, 12, branch_color))
    write_svg(output, lines)


def topology_diagnosis(entry: Dict[str, Any], exit_: Dict[str, Any]) -> Dict[str, Any]:
    entry_absorbs = (
        entry["minDistanceToPitLane"] <= EXCESSIVE_PROXIMITY_METERS
        and entry["maxCurvatureSpike"] >= CURVATURE_SPIKE_FLOOR
        and entry["headingChangeDeg"] >= 30.0
    )
    exit_absorbs = (
        exit_["minDistanceToPitLane"] <= EXCESSIVE_PROXIMITY_METERS
        and exit_["maxCurvatureSpike"] >= CURVATURE_SPIKE_FLOOR
        and exit_["headingChangeDeg"] >= 30.0
    )
    return {
        "mainTrackAbsorbsPitEntry": bool(entry_absorbs),
        "mainTrackAbsorbsPitExit": bool(exit_absorbs),
        "likelyBranchingProblem": bool(entry_absorbs and exit_absorbs),
        "entryConfidence": "high" if entry_absorbs else "medium",
        "exitConfidence": "high" if exit_absorbs else "medium",
        "explanation": (
            "The suspected MainTrack breaks fall inside the 100m windows around pitManualStart and pitManualEnd. "
            "Both zones show excessive proximity to PitLaneGeometryTrimmedManual_05_05 together with local curvature and heading anomalies. "
            "That pattern is more consistent with a merge/diverge topology branch being absorbed into a single centerline than with isolated local noise."
        ),
    }


def build() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    main = read_json(MAIN_TRACK_CACHE)
    manual = read_json(MANUAL_TRIM_JSON)
    surface = optional_json(PITLANE_SURFACE_JSON)
    surface_boundary = optional_json(PITLANE_SURFACE_BOUNDARY_JSON)
    manual_report = optional_json(MANUAL_TRIM_REPORT_JSON)
    prior_entry_exit = optional_json(ENTRY_EXIT_ZONE_ANALYSIS_JSON)
    prior_exit = optional_json(PIT_EXIT_CORE_ANALYSIS_JSON)

    main_center = points_xy(main["centerline"])
    main_width = [float(width) for width in main.get("localWidth", [])]
    if len(main_width) != len(main_center):
        left = points_xy(main.get("boundsLeft", []))
        right = points_xy(main.get("boundsRight", []))
        main_width = [distance(a, b) for a, b in zip(left, right)]
    pit_center = points_xy(manual["pitCenterline"])

    curvatures = [signed_curvature(main_center, index, closed=True) for index in range(len(main_center))]
    headings = [heading_at(main_center, index, span=3) for index in range(len(main_center))]
    abs_curvatures = [abs(value) for value in curvatures]
    curvature_stats = {
        "medianAbsCurvature": round(median(abs_curvatures), 8),
        "p95AbsCurvature": round(percentile(abs_curvatures, 0.95), 8),
        "p99AbsCurvature": round(percentile(abs_curvatures, 0.99), 8),
        "maxAbsCurvature": round(max(abs_curvatures), 8),
    }
    curvature_spike_threshold = max(CURVATURE_SPIKE_FLOOR, curvature_stats["p95AbsCurvature"])

    entry = analyze_zone(
        "entryZone",
        "pit entry",
        PIT_MANUAL_START,
        ZONE_RADIUS_METERS,
        main_center,
        main_width,
        pit_center,
        curvatures,
        headings,
        curvature_spike_threshold,
    )
    exit_ = analyze_zone(
        "exitZone",
        "pit exit",
        PIT_MANUAL_END,
        ZONE_RADIUS_METERS,
        main_center,
        main_width,
        pit_center,
        curvatures,
        headings,
        curvature_spike_threshold,
    )

    diagnosis = topology_diagnosis(entry, exit_)
    combined = {
        "generatedAt": now_iso(),
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": "debug_pit_entry_exit_breaks_combined_analysis",
        "debugOnly": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "mainTrackGeometryChanged": False,
        "trackPhysicsGeometryChanged": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "projectedPositionChanged": False,
        "lateralOffsetChanged": False,
        "mapSpaceChanged": False,
        "pitLaneGeometryChanged": False,
        "readyForRuntimeIntegration": False,
        "selectedAutomatically": False,
        "sourceFiles": {
            "mainTrackGeometry": str(MAIN_TRACK_CACHE),
            "pitLaneGeometryTrimmedManual05_05": str(MANUAL_TRIM_JSON),
            "pitLaneSurface": str(PITLANE_SURFACE_JSON),
            "pitLaneSurfaceBoundary": str(PITLANE_SURFACE_BOUNDARY_JSON),
            "manualTrimReport": str(MANUAL_TRIM_REPORT_JSON),
            "entryExitPriorAnalysis": str(ENTRY_EXIT_ZONE_ANALYSIS_JSON),
            "pitExitCorePriorAnalysis": str(PIT_EXIT_CORE_ANALYSIS_JSON),
        },
        "priorReportsLoaded": {
            "manualTrimReport": not manual_report.get("_missing", False),
            "entryExitZoneAnalysis": not prior_entry_exit.get("_missing", False),
            "pitExitCoreProblemAnalysis": not prior_exit.get("_missing", False),
            "pitLaneSurface": not surface.get("_missing", False),
            "pitLaneSurfaceBoundary": not surface_boundary.get("_missing", False),
        },
        "pitManualStart": point_round(PIT_MANUAL_START),
        "pitManualEnd": point_round(PIT_MANUAL_END),
        "pitlaneManual05_05": {
            "pointCount": len(pit_center),
            "lengthMeters": round(float(manual.get("lengthMeters") or polyline_length(pit_center)), 6),
            "removedStartMeters": float(manual.get("removedStartMeters") or 0.0),
            "removedEndMeters": float(manual.get("removedEndMeters") or 0.0),
            "aggressiveTrimRejected": bool(manual.get("aggressiveTrimRejected", True)),
            "runtimeChanged": bool(manual.get("runtimeChanged", False)),
        },
        "thresholds": {
            "zoneRadiusMeters": ZONE_RADIUS_METERS,
            "curvatureSpikeThreshold": round(curvature_spike_threshold, 8),
            "suspectProximityMeters": SUSPECT_PROXIMITY_METERS,
            "excessiveProximityMeters": EXCESSIVE_PROXIMITY_METERS,
            "headingChangeAbnormalDeg": HEADING_CHANGE_ABNORMAL_DEG,
            "widthVariationAbnormalMeters": WIDTH_VARIATION_ABNORMAL_METERS,
        },
        "curvatureStats": curvature_stats,
        "entryZone": entry,
        "exitZone": exit_,
        "topologyDiagnosis": diagnosis,
        "exports": {
            "combinedAnalysisJson": str(COMBINED_ANALYSIS_JSON),
            "combinedAnalysisSvg": str(COMBINED_ANALYSIS_SVG),
            "entryCandidateJson": str(ENTRY_CANDIDATE_JSON),
            "entryCandidateSvg": str(ENTRY_CANDIDATE_SVG),
            "exitCandidateJson": str(EXIT_CANDIDATE_JSON),
            "exitCandidateSvg": str(EXIT_CANDIDATE_SVG),
            "pitEntryTransitionCandidatesJson": str(ENTRY_TRANSITION_JSON),
            "pitEntryTransitionCandidatesSvg": str(ENTRY_TRANSITION_SVG),
            "pitExitTransitionCandidatesJson": str(EXIT_TRANSITION_JSON),
            "pitExitTransitionCandidatesSvg": str(EXIT_TRANSITION_SVG),
            "finalReportJson": str(FINAL_REPORT_JSON),
        },
    }
    COMBINED_ANALYSIS_JSON.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    write_combined_svg(main_center, pit_center, entry, exit_)

    entry_candidate = build_maintrack_candidate(
        "entryZone",
        "debug_maintrack_entry_zone_candidate",
        entry,
        main_center,
        main_width,
        pit_center,
        ENTRY_CANDIDATE_JSON,
        ENTRY_CANDIDATE_SVG,
    )
    exit_candidate = build_maintrack_candidate(
        "exitZone",
        "debug_maintrack_exit_zone_candidate_v2",
        exit_,
        main_center,
        main_width,
        pit_center,
        EXIT_CANDIDATE_JSON,
        EXIT_CANDIDATE_SVG,
    )
    entry_transitions = build_entry_transition_candidates(entry, main_center, pit_center, curvatures)
    exit_transitions = build_exit_transition_candidates(exit_, main_center, pit_center, curvatures)

    final_report = {
        "generatedAt": now_iso(),
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": "debug_pit_entry_exit_breaks_final_report",
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "entryBreakDetected": bool(diagnosis["mainTrackAbsorbsPitEntry"]),
        "exitBreakDetected": bool(diagnosis["mainTrackAbsorbsPitExit"]),
        "entrySuspectedIndices": entry["suspectedIndices"],
        "exitSuspectedIndices": exit_["suspectedIndices"],
        "entryCandidateGenerated": bool(entry_candidate.get("candidateSegment")),
        "exitCandidateGenerated": bool(exit_candidate.get("candidateSegment")),
        "pitEntryTransitionCandidatesGenerated": bool(entry_transitions.get("candidates")),
        "pitExitTransitionCandidatesGenerated": bool(exit_transitions.get("candidates")),
        "readyForRuntimeIntegration": False,
        "recommendedNextStep": (
            "Inspect the combined and candidate SVGs, compare branch candidates manually, and only then decide whether a separate topology-aware "
            "runtime integration plan is needed. Do not promote any generated candidate automatically."
        ),
        "exports": combined["exports"],
    }
    FINAL_REPORT_JSON.write_text(json.dumps(final_report, indent=2), encoding="utf-8")

    print(COMBINED_ANALYSIS_JSON)
    print(ENTRY_CANDIDATE_JSON)
    print(EXIT_CANDIDATE_JSON)
    print(ENTRY_TRANSITION_JSON)
    print(EXIT_TRANSITION_JSON)
    print(FINAL_REPORT_JSON)


if __name__ == "__main__":
    build()
