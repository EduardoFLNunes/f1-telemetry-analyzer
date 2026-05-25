from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Sequence, Tuple
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"

PROBLEM_JSON = "interlagos_reta_oposta_local_problem_window.json"
PROBLEM_SVG = "interlagos_reta_oposta_local_problem_window.svg"
CANDIDATE_JSON = "interlagos_reta_oposta_local_fix_candidate.json"
CANDIDATE_SVG = "interlagos_reta_oposta_local_fix_candidate.svg"
VALIDATION_JSON = "interlagos_reta_oposta_local_fix_validation.json"
VALIDATION_SVG = "interlagos_reta_oposta_local_fix_validation.svg"

GEOMETRY_NAME = "InterlagosRetaOpostaLocalFix"
API_TRACK_GEOMETRY = "http://127.0.0.1:8000/api/track/geometry"

Point = Tuple[float, float]


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    context = _load_context()
    problem = _detect_problem_window(context)
    candidate = _build_candidate(context, problem)
    validation = _validate_candidate(context, problem, candidate)

    (DEBUG_DIR / PROBLEM_JSON).write_text(json.dumps(problem, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / PROBLEM_SVG).write_text(_problem_svg(context, problem), encoding="utf-8")
    (DEBUG_DIR / CANDIDATE_JSON).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / CANDIDATE_SVG).write_text(_candidate_svg(context, problem, candidate), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_JSON).write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_SVG).write_text(_validation_svg(context, problem, candidate, validation), encoding="utf-8")

    print(
        {
            "problem": str(DEBUG_DIR / PROBLEM_JSON),
            "candidate": str(DEBUG_DIR / CANDIDATE_JSON),
            "validation": str(DEBUG_DIR / VALIDATION_JSON),
            "passed": validation["passed"],
            "window": {"startIndex": problem["startIndex"], "endIndex": problem["endIndex"]},
        }
    )


def _load_context() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_GEOMETRY, timeout=10).read().decode("utf-8"))
    track = payload.get("track") or {}
    if not track:
        raise RuntimeError("Active app track geometry is not available")

    edge_debug = json.loads((DEBUG_DIR / "track_edges_interval_raycast_vhe_interlagos.json").read_text(encoding="utf-8"))
    edge_candidate = json.loads((DEBUG_DIR / "interlagos_edge_continuity_fix_candidate.json").read_text(encoding="utf-8"))

    center = _arrays_to_points(track.get("centerline", {}))
    left = _arrays_to_points(track.get("left_edge", {}))
    right = _arrays_to_points(track.get("right_edge", {}))
    widths = [float(value) for value in track.get("localWidth", [])]
    fast = [_tuple(sample["fastLane"]) for sample in edge_debug.get("edges", {}).get("samples", [])]
    candidate_left = [_tuple(point) for point in edge_candidate.get("leftEdge", {}).get("points", [])]
    candidate_right = [_tuple(point) for point in edge_candidate.get("rightEdge", {}).get("points", [])]

    count = min(len(center), len(left), len(right), len(widths), len(fast), len(candidate_left), len(candidate_right))
    if count <= 0:
        raise RuntimeError("Interlagos geometry inputs are incomplete")

    return {
        "apiPayload": payload,
        "track": track,
        "center": center[:count],
        "left": left[:count],
        "right": right[:count],
        "widths": widths[:count],
        "fast": fast[:count],
        "candidateLeft": candidate_left[:count],
        "candidateRight": candidate_right[:count],
        "count": count,
        "sourceProvider": track.get("provider"),
    }


def _detect_problem_window(context: Dict[str, Any]) -> Dict[str, Any]:
    center = context["center"]
    left = context["left"]
    right = context["right"]
    widths = context["widths"]
    fast = context["fast"]

    search_start = 420
    search_end = 560
    distances_to_fast = [_distance(center[index], fast[index]) for index in range(search_start, search_end + 1)]
    stable_reference = median(distances_to_fast[-25:])
    threshold = max(1.0, stable_reference * 4.0)
    suspect_indices = [
        index
        for index in range(search_start, search_end + 1)
        if _distance(center[index], fast[index]) > threshold
    ]
    if not suspect_indices:
        start_index, end_index = 425, 530
    else:
        first = suspect_indices[0]
        last = suspect_indices[-1]
        start_index = max(search_start, first - 5)
        end_index = min(search_end, last + 5)
        for index in range(last + 1, search_end - 2):
            if max(_distance(center[j], fast[j]) for j in range(index, index + 3)) < 0.3:
                end_index = min(search_end, index + 5)
                break

    heading_variation = _heading_variation(center, start_index, end_index)
    heading_oscillation = _heading_oscillation(center, start_index, end_index)
    curvature_profile = [
        {
            "index": index,
            "headingDeg": round(_heading_at(center, index) * 180.0 / math.pi, 6),
            "curvatureDeg": round(_curvature_at(center, index) * 180.0 / math.pi, 6),
            "distanceToFastLane": round(_distance(center[index], fast[index]), 6),
        }
        for index in range(start_index, end_index + 1)
    ]
    width_profile = [
        {"index": index, "width": round(widths[index], 6)}
        for index in range(start_index, end_index + 1)
    ]
    edge_steps = {
        "leftMaxStep": round(max(_steps(left)[start_index + 1 : end_index + 1] or [0.0]), 6),
        "rightMaxStep": round(max(_steps(right)[start_index + 1 : end_index + 1] or [0.0]), 6),
        "leftJumpCount": _jump_count(left, start_index, end_index),
        "rightJumpCount": _jump_count(right, start_index, end_index),
    }

    return {
        "name": "InterlagosRetaOpostaLocalProblemWindow",
        "generatedAt": datetime.utcnow().isoformat(),
        "sourceProvider": context["sourceProvider"],
        "searchRange": {"startIndex": search_start, "endIndex": search_end},
        "startIndex": start_index,
        "endIndex": end_index,
        "problem": "saida da Curva do Sol / entrada da Reta Oposta",
        "headingVariation": round(heading_variation, 6),
        "centerlineHeadingOscillation": round(heading_oscillation, 6),
        "curvatureProfile": curvature_profile,
        "widthProfile": width_profile,
        "localEdgeIdentityStability": {
            **edge_steps,
            "centerToFastDistanceMax": round(max(_distance(center[i], fast[i]) for i in range(start_index, end_index + 1)), 6),
            "centerToFastDistanceMedian": round(median(_distance(center[i], fast[i]) for i in range(start_index, end_index + 1)), 6),
            "detectedBy": "centerline-to-fast-lane deviation plus short heading oscillation",
        },
    }


def _build_candidate(context: Dict[str, Any], problem: Dict[str, Any]) -> Dict[str, Any]:
    start = int(problem["startIndex"])
    end = int(problem["endIndex"])
    before_center = context["center"]
    before_left = context["left"]
    before_right = context["right"]
    before_widths = context["widths"]
    fast = context["fast"]

    after_center = list(before_center)
    after_left = list(before_left)
    after_right = list(before_right)
    after_widths = list(before_widths)
    corrected_indices = list(range(start, end + 1))

    for index in corrected_indices:
        after_center[index] = fast[index]
    normals = _continuous_normals(after_center, before_left)
    for index in corrected_indices:
        half_width = before_widths[index] * 0.5
        normal = normals[index]
        center = after_center[index]
        after_left[index] = (center[0] + normal[0] * half_width, center[1] + normal[1] * half_width)
        after_right[index] = (center[0] - normal[0] * half_width, center[1] - normal[1] * half_width)
        after_widths[index] = before_widths[index]

    generated_at = datetime.utcnow().isoformat()
    return {
        "name": "vhe_interlagos",
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "geometryName": GEOMETRY_NAME,
        "visualGeometryName": GEOMETRY_NAME,
        "renderMode": "visual_local_reta_oposta_fix",
        "generatedAt": generated_at,
        "updatedAt": generated_at,
        "sourceProvider": context["sourceProvider"],
        "coordinateSystem": "map_xy_from_world_x_negative_z",
        "projectionCenterlinePreserved": True,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "localFix": {
            "region": "saida da Curva do Sol / entrada da Reta Oposta",
            "startIndex": start,
            "endIndex": end,
            "correctedIndexCount": len(corrected_indices),
            "method": "local visual centerline follows fast_lane.ai; left/right edges rebuilt from the corrected centerline and preserved local width only inside the local window",
            "globalRebuild": False,
        },
        "centerline": _polyline(after_center),
        "visualCenterline": _polyline(after_center),
        "projectionCenterlineOriginal": _polyline(before_center),
        "leftEdge": _polyline(after_left),
        "rightEdge": _polyline(after_right),
        "localWidth": [round(value, 6) for value in after_widths],
        "widthMin": round(min(after_widths), 6),
        "widthAvg": round(sum(after_widths) / len(after_widths), 6),
        "widthMax": round(max(after_widths), 6),
        "bounds": _bounds([*after_left, *after_right, *after_center]),
        "asphaltPolygon": _polyline(after_left + list(reversed(after_right))),
    }


def _validate_candidate(context: Dict[str, Any], problem: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    start = int(problem["startIndex"])
    end = int(problem["endIndex"])
    before_center = context["center"]
    before_left = context["left"]
    before_right = context["right"]
    before_widths = context["widths"]
    after_center = [_tuple(point) for point in candidate["centerline"]["points"]]
    after_left = [_tuple(point) for point in candidate["leftEdge"]["points"]]
    after_right = [_tuple(point) for point in candidate["rightEdge"]["points"]]
    after_widths = [float(value) for value in candidate["localWidth"]]

    width_deltas = [abs(after_widths[index] - before_widths[index]) for index in range(start, end + 1)]
    center_shifts = [_distance(after_center[index], before_center[index]) for index in range(start, end + 1)]
    tail_start = max(start, min(end - 8, 480))
    tail_end = min(end, max(tail_start + 8, 530))
    before_osc = _heading_oscillation(before_center, start, end)
    after_osc = _heading_oscillation(after_center, start, end)
    before_tail_osc = _heading_oscillation(before_center, tail_start, tail_end)
    after_tail_osc = _heading_oscillation(after_center, tail_start, tail_end)
    after_tail_chord = _max_chord_deviation(after_center, tail_start, tail_end)

    fields = {
        "miniUndulationRemoved": after_osc < before_osc * 0.2 and after_tail_osc < 5.0,
        "fakeChicaneRemoved": _x_reversal_count(after_center, start, end) == 0,
        "entryToRetaOpostaLooksStraight": after_tail_chord <= 1.0 and after_tail_osc <= 5.0,
        "widthCollapseCountBefore": _width_collapse_count(before_widths, start, end),
        "widthCollapseCountAfter": _width_collapse_count(after_widths, start, end),
        "leftEdgeJumpCountBefore": _jump_count(before_left, start, end),
        "leftEdgeJumpCountAfter": _jump_count(after_left, start, end),
        "rightEdgeJumpCountBefore": _jump_count(before_right, start, end),
        "rightEdgeJumpCountAfter": _jump_count(after_right, start, end),
        "centerlineHeadingOscillationBefore": round(before_osc, 6),
        "centerlineHeadingOscillationAfter": round(after_osc, 6),
        "centerlineHeadingOscillationTailBefore": round(before_tail_osc, 6),
        "centerlineHeadingOscillationTailAfter": round(after_tail_osc, 6),
        "widthDeltaAvg": round(sum(width_deltas) / len(width_deltas), 6),
        "widthDeltaP95": round(_percentile(width_deltas, 0.95), 6),
        "widthDeltaMax": round(max(width_deltas), 6),
        "centerlineShiftAvg": round(sum(center_shifts) / len(center_shifts), 6),
        "centerlineShiftP95": round(_percentile(center_shifts, 0.95), 6),
        "centerlineShiftMax": round(max(center_shifts), 6),
        "holesRemaining": 0 if max(_max_segment(after_left), _max_segment(after_right), _max_segment(after_center)) <= 30.0 else 1,
        "linesCrossingTrack": _polygon_self_intersects(after_left + list(reversed(after_right))),
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "localWindow": {"startIndex": start, "endIndex": end, "straightTailStartIndex": tail_start, "straightTailEndIndex": tail_end},
        "tailChordDeviationAfter": round(after_tail_chord, 6),
    }
    passed = (
        fields["miniUndulationRemoved"]
        and fields["fakeChicaneRemoved"]
        and fields["entryToRetaOpostaLooksStraight"]
        and fields["holesRemaining"] == 0
        and not fields["linesCrossingTrack"]
        and fields["widthCollapseCountAfter"] == 0
        and fields["leftEdgeJumpCountAfter"] == 0
        and fields["rightEdgeJumpCountAfter"] == 0
        and fields["widthDeltaAvg"] <= 0.05
        and fields["widthDeltaP95"] <= 0.15
        and fields["widthDeltaMax"] <= 0.35
    )
    return {
        "name": "InterlagosRetaOpostaLocalFixValidation",
        "generatedAt": datetime.utcnow().isoformat(),
        "candidateGeometry": GEOMETRY_NAME,
        "passed": passed,
        **fields,
    }


def _arrays_to_points(payload: Dict[str, Any]) -> List[Point]:
    x = payload.get("x", [])
    y = payload.get("y", payload.get("z", []))
    return [(float(px), float(py)) for px, py in zip(x, y)]


def _tuple(point: Sequence[float]) -> Point:
    return (float(point[0]), float(point[1]))


def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _steps(points: Sequence[Point]) -> List[float]:
    return [0.0] + [_distance(points[index - 1], points[index]) for index in range(1, len(points))]


def _heading_at(points: Sequence[Point], index: int) -> float:
    prev_index = max(0, index - 1)
    next_index = min(len(points) - 1, index + 1)
    dx = points[next_index][0] - points[prev_index][0]
    dy = points[next_index][1] - points[prev_index][1]
    return math.atan2(dy, dx)


def _curvature_at(points: Sequence[Point], index: int) -> float:
    if index <= 0 or index >= len(points) - 1:
        return 0.0
    return _angle_delta(_heading_at(points, index + 1), _heading_at(points, index - 1))


def _heading_variation(points: Sequence[Point], start: int, end: int) -> float:
    return abs(_angle_delta(_heading_at(points, end), _heading_at(points, start))) * 180.0 / math.pi


def _heading_oscillation(points: Sequence[Point], start: int, end: int) -> float:
    headings = [_heading_at(points, index) for index in range(start, end + 1)]
    return sum(abs(_angle_delta(headings[index], headings[index - 1])) for index in range(1, len(headings))) * 180.0 / math.pi


def _angle_delta(a: float, b: float) -> float:
    delta = a - b
    while delta > math.pi:
        delta -= math.tau
    while delta < -math.pi:
        delta += math.tau
    return delta


def _x_reversal_count(points: Sequence[Point], start: int, end: int) -> int:
    count = 0
    previous_sign = 0
    for index in range(start + 1, end + 1):
        dx = points[index][0] - points[index - 1][0]
        sign = 1 if dx > 1e-6 else -1 if dx < -1e-6 else 0
        if previous_sign and sign and sign != previous_sign:
            count += 1
        if sign:
            previous_sign = sign
    return count


def _continuous_normals(points: Sequence[Point], reference_left: Sequence[Point]) -> List[Point]:
    normals: List[Point] = []
    for index in range(len(points)):
        prev_point = points[(index - 1) % len(points)]
        next_point = points[(index + 1) % len(points)]
        dx = next_point[0] - prev_point[0]
        dy = next_point[1] - prev_point[1]
        length = math.hypot(dx, dy) or 1.0
        normals.append((-dy / length, dx / length))

    if normals and reference_left:
        first = normals[0]
        if (reference_left[0][0] - points[0][0]) * first[0] + (reference_left[0][1] - points[0][1]) * first[1] < 0:
            normals[0] = (-first[0], -first[1])
    for index in range(1, len(normals)):
        previous = normals[index - 1]
        current = normals[index]
        if previous[0] * current[0] + previous[1] * current[1] < 0:
            normals[index] = (-current[0], -current[1])
    return normals


def _jump_count(points: Sequence[Point], start: int, end: int) -> int:
    steps = _steps(points)
    local = [steps[index] for index in range(max(1, start), min(len(steps) - 1, end) + 1)]
    local_median = median(local) if local else 0.0
    threshold = max(3.0, local_median * 3.0)
    return sum(1 for index in range(max(1, start), end + 1) if steps[index] > threshold)


def _width_collapse_count(widths: Sequence[float], start: int, end: int) -> int:
    local = widths[max(0, start - 20) : min(len(widths), end + 21)]
    local_median = median(local) if local else 0.0
    return sum(1 for index in range(start, end + 1) if widths[index] < local_median * 0.65)


def _percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return float(ordered[index])


def _max_segment(points: Sequence[Point]) -> float:
    return max((_distance(points[index - 1], points[index]) for index in range(1, len(points))), default=0.0)


def _max_chord_deviation(points: Sequence[Point], start: int, end: int) -> float:
    a = points[start]
    b = points[end]
    vx = b[0] - a[0]
    vy = b[1] - a[1]
    length = math.hypot(vx, vy) or 1.0
    return max(abs((points[index][0] - a[0]) * vy - (points[index][1] - a[1]) * vx) / length for index in range(start, end + 1))


def _polygon_self_intersects(points: Sequence[Point]) -> bool:
    segments = list(zip(points, points[1:] + points[:1]))
    for i, (a1, a2) in enumerate(segments):
        for j in range(i + 1, len(segments)):
            if abs(i - j) <= 1 or (i == 0 and j == len(segments) - 1):
                continue
            b1, b2 = segments[j]
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    if max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0]):
        return False
    if max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1]):
        return False

    def orient(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return orient(a, b, c) * orient(a, b, d) < 0 and orient(c, d, a) * orient(c, d, b) < 0


def _polyline(points: Sequence[Point]) -> Dict[str, Any]:
    rounded = [[round(point[0], 6), round(point[1], 6)] for point in points]
    return {
        "points": rounded,
        "x": [point[0] for point in rounded],
        "y": [point[1] for point in rounded],
    }


def _bounds(points: Sequence[Point]) -> Dict[str, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "minX": round(min(xs), 6),
        "maxX": round(max(xs), 6),
        "minY": round(min(ys), 6),
        "maxY": round(max(ys), 6),
    }


def _problem_svg(context: Dict[str, Any], problem: Dict[str, Any]) -> str:
    return _svg(
        "Interlagos Reta Oposta local problem window",
        context,
        problem,
        after=None,
        footer=f"Detected local window {problem['startIndex']}-{problem['endIndex']}",
    )


def _candidate_svg(context: Dict[str, Any], problem: Dict[str, Any], candidate: Dict[str, Any]) -> str:
    return _svg("Interlagos Reta Oposta local fix candidate", context, problem, after=candidate)


def _validation_svg(context: Dict[str, Any], problem: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    footer = f"passed={validation['passed']} oscillation {validation['centerlineHeadingOscillationBefore']} -> {validation['centerlineHeadingOscillationAfter']}"
    return _svg("Interlagos Reta Oposta local fix validation", context, problem, after=candidate, footer=footer)


def _svg(title: str, context: Dict[str, Any], problem: Dict[str, Any], after: Dict[str, Any] | None, footer: str = "") -> str:
    start = max(0, int(problem["startIndex"]) - 35)
    end = min(context["count"] - 1, int(problem["endIndex"]) + 35)
    before_center = context["center"][start : end + 1]
    before_left = context["left"][start : end + 1]
    before_right = context["right"][start : end + 1]
    fast = context["fast"][start : end + 1]
    if after:
        after_center = [_tuple(point) for point in after["centerline"]["points"]][start : end + 1]
        after_left = [_tuple(point) for point in after["leftEdge"]["points"]][start : end + 1]
        after_right = [_tuple(point) for point in after["rightEdge"]["points"]][start : end + 1]
    else:
        after_center = after_left = after_right = []

    all_points = [*before_center, *before_left, *before_right, *fast, *after_center, *after_left, *after_right]
    bounds = _bounds(all_points)
    width = 1200
    height = 900
    pad = 70
    sx = (width - 2 * pad) / max(bounds["maxX"] - bounds["minX"], 1.0)
    sy = (height - 2 * pad) / max(bounds["maxY"] - bounds["minY"], 1.0)
    scale = min(sx, sy)

    def project(point: Point) -> Tuple[float, float]:
        return (
            pad + (point[0] - bounds["minX"]) * scale,
            height - pad - (point[1] - bounds["minY"]) * scale,
        )

    def path(points: Sequence[Point]) -> str:
        if not points:
            return ""
        projected = [project(point) for point in points]
        return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in projected)

    marker_indices = [problem["startIndex"], problem["endIndex"], 480, 500, 530]
    markers = []
    for index in marker_indices:
        if start <= index <= end:
            point = context["fast"][index]
            x, y = project(point)
            markers.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="#fbbf24"/>')
            markers.append(f'<text x="{x + 8:.2f}" y="{y - 8:.2f}" fill="#f8fafc" font-size="15">{index}</text>')

    after_layers = ""
    if after:
        after_layers = f"""
  <path d="{path(after_left)}" fill="none" stroke="#22d3ee" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path(after_right)}" fill="none" stroke="#67e8f9" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path(after_center)}" fill="none" stroke="#a7f3d0" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#071018"/>
  <text x="30" y="38" fill="#e2e8f0" font-size="22" font-family="Segoe UI, Arial">{_xml(title)}</text>
  <text x="30" y="64" fill="#94a3b8" font-size="13" font-family="Segoe UI, Arial">before red, after cyan, fast_lane purple dashed</text>
  <path d="{path(before_left)}" fill="none" stroke="#ef4444" stroke-opacity="0.42" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path(before_right)}" fill="none" stroke="#f97316" stroke-opacity="0.42" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path(before_center)}" fill="none" stroke="#f43f5e" stroke-opacity="0.78" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path(fast)}" fill="none" stroke="#c084fc" stroke-width="2" stroke-dasharray="8 10" stroke-linecap="round" stroke-linejoin="round"/>
  {after_layers}
  {''.join(markers)}
  <text x="30" y="{height - 30}" fill="#94a3b8" font-size="14" font-family="Segoe UI, Arial">{_xml(footer)}</text>
</svg>
"""


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    main()
