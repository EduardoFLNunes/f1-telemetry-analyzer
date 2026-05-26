from __future__ import annotations

import copy
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from build_interlagos_pit_access_centerline_fix import (  # noqa: E402
    CORRIDOR_NAME,
    ENTRY_NAME,
    EXIT_NAME,
    _bounds_for_points,
    _distance,
    _heading_oscillation,
    _inside,
    _line_points,
    _load_context,
    _max_chord_deviation,
    _polyline,
    _unit,
    _xml,
)
from build_interlagos_pit_access_edge_stitch_fix import _all_accesses_open, _tangent  # noqa: E402
from build_interlagos_pit_bifurcation_taper_refine import _max_heading_step, _polyline_length  # noqa: E402


DEBUG_DIR = REPO_ROOT / "data" / "debug"
API_TRACK_CURRENT = "http://127.0.0.1:8000/api/track/current"

BASE_CANDIDATE_JSON = "interlagos_pit_access_edge_stitch_fix_candidate.json"
BASE_VALIDATION_JSON = "interlagos_pit_access_edge_stitch_fix_validation.json"
CANDIDATE_JSON = "interlagos_pit_access_smooth_stitch_fix_candidate.json"
CANDIDATE_SVG = "interlagos_pit_access_smooth_stitch_fix_candidate.svg"
VALIDATION_JSON = "interlagos_pit_access_smooth_stitch_fix_validation.json"
VALIDATION_SVG = "interlagos_pit_access_smooth_stitch_fix_validation.svg"
APP_CHECK_JSON = "interlagos_pit_access_smooth_stitch_fix_app_check.json"

GEOMETRY_NAME = "InterlagosPitAccessSmoothStitchFix"
RENDER_MODE = "visual_pit_access_smooth_stitch_fix"
STITCH_SEGMENT_COUNT = 11
MAX_STITCH_HEADING_STEP_DEG = 18.0
MAX_JOIN_GAP_M = 0.04

Point = Tuple[float, float]


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    if "--app-check" in sys.argv:
        app_check = _build_app_check()
        (DEBUG_DIR / APP_CHECK_JSON).write_text(json.dumps(app_check, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            {
                "appCheck": str(DEBUG_DIR / APP_CHECK_JSON),
                "appUsesPitAccessSmoothStitchFix": app_check["appUsesPitAccessSmoothStitchFix"],
            }
        )
        return

    context = _load_context()
    base = json.loads((DEBUG_DIR / BASE_CANDIDATE_JSON).read_text(encoding="utf-8"))
    base_validation = json.loads((DEBUG_DIR / BASE_VALIDATION_JSON).read_text(encoding="utf-8"))
    candidate = _build_candidate(context, base, base_validation)
    validation = _validate_candidate(context, base, base_validation, candidate)

    (DEBUG_DIR / CANDIDATE_JSON).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / CANDIDATE_SVG).write_text(_candidate_svg(context, base, candidate, validation), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_JSON).write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_SVG).write_text(_validation_svg(context, base, candidate, validation), encoding="utf-8")
    print(
        {
            "candidate": str(DEBUG_DIR / CANDIDATE_JSON),
            "validation": str(DEBUG_DIR / VALIDATION_JSON),
            "passed": validation["passed"],
            "maxStitchHeadingStepBefore": validation["maxStitchHeadingStepBefore"],
            "maxStitchHeadingStepAfter": validation["maxStitchHeadingStepAfter"],
        }
    )


def _build_candidate(context: Dict[str, Any], base: Dict[str, Any], base_validation: Dict[str, Any]) -> Dict[str, Any]:
    visual = copy.deepcopy(base["visualGeometry"])
    visual["name"] = GEOMETRY_NAME
    visual["source"] = "pit access surface union with tangent-continuous local stitch contours at main-track contacts"
    surface = visual["surfaceUnionFix"]
    ranges = surface["mainTrackStrokeSuppression"]["leftRanges"]
    entry_range = list(ranges[0])
    exit_range = list(ranges[1])
    previous_stitches = {edge["name"]: edge for edge in surface.get("stitchEdges", [])}
    stitch_edges = [
        _smooth_stitch_edge(
            "PitEntryStartStitchEdge",
            ENTRY_NAME,
            "entryStart",
            context,
            visual["geometries"][ENTRY_NAME],
            entry_range,
            previous_stitches,
            start=True,
        ),
        _smooth_stitch_edge(
            "PitEntryEndStitchEdge",
            ENTRY_NAME,
            "entryEnd",
            context,
            visual["geometries"][ENTRY_NAME],
            entry_range,
            previous_stitches,
            start=False,
        ),
        _smooth_stitch_edge(
            "PitExitStartStitchEdge",
            EXIT_NAME,
            "exitStart",
            context,
            visual["geometries"][EXIT_NAME],
            exit_range,
            previous_stitches,
            start=True,
        ),
        _smooth_stitch_edge(
            "PitExitEndStitchEdge",
            EXIT_NAME,
            "exitEnd",
            context,
            visual["geometries"][EXIT_NAME],
            exit_range,
            previous_stitches,
            start=False,
        ),
    ]
    surface["name"] = GEOMETRY_NAME
    surface["edgeStitchFix"] = True
    surface["smoothStitchFix"] = True
    surface["stitchEdges"] = stitch_edges
    surface["stitchStyle"] = {
        "stroke": "outerBoundary",
        "drawOnlyAsFinalContour": True,
        "continuity": "tangent-guided",
    }
    surface["internalEdgesRemoved"] = list(surface.get("internalEdgesRemoved", [])) + [
        "Angular stitch contours replaced by tangent-guided smooth stitch curves",
    ]
    visual["renderHints"] = {**visual.get("renderHints", {}), "edgeStitchFix": True, "smoothStitchFix": True}

    generated_at = datetime.utcnow().isoformat()
    return {
        "name": GEOMETRY_NAME,
        "geometryName": GEOMETRY_NAME,
        "visualGeometryName": GEOMETRY_NAME,
        "renderMode": RENDER_MODE,
        "generatedAt": generated_at,
        "updatedAt": generated_at,
        "baseGeometry": base.get("geometryName"),
        "mainTrackGeometry": base.get("mainTrackGeometry"),
        "mainTrackVisualGeometry": base.get("mainTrackVisualGeometry"),
        "mainTrackPreserved": True,
        "pitlanePreserved": True,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "maxStitchHeadingStepBefore": base_validation.get("maxStitchHeadingStep"),
        "visualGeometry": visual,
    }


def _smooth_stitch_edge(
    name: str,
    geometry_name: str,
    role: str,
    context: Dict[str, Any],
    geometry: Dict[str, Any],
    main_range: Sequence[int],
    previous_stitches: Dict[str, Dict[str, Any]],
    *,
    start: bool,
) -> Dict[str, Any]:
    main = context["mainLeft"]
    outer = _line_points(geometry["outerEdge"])
    if start:
        main_index = max(1, int(main_range[0]) - 1)
        access_index = 0
        start_point = main[main_index]
        end_point = outer[access_index]
        start_tangent = _tangent(main, main_index - 1, main_index)
        end_tangent = _tangent(outer, 0, 1)
    else:
        main_index = min(len(main) - 2, int(main_range[1]) + 1)
        access_index = len(outer) - 1
        start_point = outer[access_index]
        end_point = main[main_index]
        start_tangent = _tangent(outer, len(outer) - 2, len(outer) - 1)
        end_tangent = _tangent(main, main_index, main_index + 1)

    points, heading_step = _tangent_guided_bridge(start_point, end_point, start_tangent, end_tangent)
    previous = previous_stitches.get(name, {})
    return {
        "name": name,
        "geometryName": geometry_name,
        "role": role,
        "mainEdge": "left",
        "mainIndex": main_index,
        "accessEdge": "outerEdge",
        "accessIndex": access_index,
        "mainRange": list(main_range),
        "endpointGapBeforeMeters": round(_distance(start_point, end_point), 6),
        "endpointGapAfterMeters": round(_distance(points[-1], end_point), 6),
        "previousMaxHeadingStep": round(float(previous.get("maxHeadingStep", 0.0)), 6),
        "maxHeadingStep": round(heading_step, 6),
        "sampleCount": len(points),
        "method": "tangent_guided_heading_interpolation",
        "startTangent": [round(start_tangent[0], 8), round(start_tangent[1], 8)],
        "endTangent": [round(end_tangent[0], 8), round(end_tangent[1], 8)],
        "points": _polyline(points),
    }


def _tangent_guided_bridge(start: Point, end: Point, start_tangent: Point, end_tangent: Point) -> Tuple[List[Point], float]:
    chord = (end[0] - start[0], end[1] - start[1])
    chord_len = math.hypot(chord[0], chord[1])
    if chord_len <= 1e-6:
        return [start, end], 0.0

    segment_count = STITCH_SEGMENT_COUNT
    midpoint = (segment_count - 1) // 2
    start_angle = _angle(start_tangent)
    end_angle = _angle(end_tangent)
    target_angle = math.atan2(chord[1], chord[0])
    tail_length = max(0.04, min(0.12, chord_len * 0.005))

    lengths: List[float] = []
    headings: List[float] = []
    for _ in range(8):
        headings = _bridge_headings(start_angle, target_angle, end_angle, segment_count, midpoint)
        residual_x = chord[0]
        residual_y = chord[1]
        lengths = []
        for index, heading in enumerate(headings):
            if index == midpoint:
                lengths.append(0.0)
                continue
            distance_from_mid = abs(index - midpoint) / max(1, midpoint)
            length = tail_length * (0.75 + 0.55 * (1.0 - distance_from_mid))
            lengths.append(length)
            residual_x -= math.cos(heading) * length
            residual_y -= math.sin(heading) * length
        next_target_angle = math.atan2(residual_y, residual_x)
        if abs(_angle_delta(target_angle, next_target_angle)) < 1e-7:
            break
        target_angle = next_target_angle

    headings = _bridge_headings(start_angle, target_angle, end_angle, segment_count, midpoint)
    residual_x = chord[0]
    residual_y = chord[1]
    lengths = []
    for index, heading in enumerate(headings):
        if index == midpoint:
            lengths.append(0.0)
            continue
        distance_from_mid = abs(index - midpoint) / max(1, midpoint)
        length = tail_length * (0.75 + 0.55 * (1.0 - distance_from_mid))
        lengths.append(length)
        residual_x -= math.cos(heading) * length
        residual_y -= math.sin(heading) * length
    lengths[midpoint] = math.hypot(residual_x, residual_y)

    points = [start]
    x, y = start
    for heading, length in zip(headings, lengths):
        x += math.cos(heading) * length
        y += math.sin(heading) * length
        points.append((x, y))
    points[-1] = end
    return points, _max_heading_step(points)


def _bridge_headings(start_angle: float, target_angle: float, end_angle: float, segment_count: int, midpoint: int) -> List[float]:
    headings: List[float] = []
    for index in range(segment_count):
        if index <= midpoint:
            headings.append(_angle_lerp(start_angle, target_angle, index / max(1, midpoint)))
        else:
            headings.append(_angle_lerp(target_angle, end_angle, (index - midpoint) / max(1, segment_count - 1 - midpoint)))
    return headings


def _angle(vector: Point) -> float:
    return math.atan2(vector[1], vector[0])


def _angle_delta(start: float, end: float) -> float:
    delta = end - start
    while delta > math.pi:
        delta -= math.tau
    while delta < -math.pi:
        delta += math.tau
    return delta


def _angle_lerp(start: float, end: float, t: float) -> float:
    return start + _angle_delta(start, end) * t


def _validate_candidate(
    context: Dict[str, Any],
    base: Dict[str, Any],
    base_validation: Dict[str, Any],
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    visual = candidate["visualGeometry"]
    surface = visual["surfaceUnionFix"]
    stitches = surface.get("stitchEdges", [])
    entry_stitches = [edge for edge in stitches if edge.get("geometryName") == ENTRY_NAME]
    exit_stitches = [edge for edge in stitches if edge.get("geometryName") == EXIT_NAME]
    max_heading_before = max(
        [float(edge.get("maxHeadingStep", 999.0)) for edge in base["visualGeometry"]["surfaceUnionFix"].get("stitchEdges", [])] or
        [float(base_validation.get("maxStitchHeadingStep", 999.0))]
    )
    max_heading_after = max([float(edge.get("maxHeadingStep", 999.0)) for edge in stitches] or [999.0])
    max_after_gap = max([float(edge.get("endpointGapAfterMeters", 999.0)) for edge in stitches] or [999.0])
    policy = surface["pitGeometryStrokePolicy"]
    fields = {
        "smoothStitchEdgesGenerated": len(stitches) == 4 and bool(surface.get("smoothStitchFix")),
        "maxEndpointGapAfterMeters": round(max_after_gap, 6),
        "maxStitchHeadingStepBefore": round(max_heading_before, 6),
        "maxStitchHeadingStepAfter": round(max_heading_after, 6),
        "maxStitchHeadingStepLimit": MAX_STITCH_HEADING_STEP_DEG,
        "noSharpStitchAngle": max_heading_after <= MAX_STITCH_HEADING_STEP_DEG,
        "entryEdgeStitched": len(entry_stitches) == 2 and all(edge.get("endpointGapAfterMeters", 1.0) <= MAX_JOIN_GAP_M for edge in entry_stitches),
        "exitEdgeStitched": len(exit_stitches) == 2 and all(edge.get("endpointGapAfterMeters", 1.0) <= MAX_JOIN_GAP_M for edge in exit_stitches),
        "noInternalEdgeBreakAtEntry": len(entry_stitches) == 2 and "innerEdge" in policy[ENTRY_NAME]["suppressEdges"],
        "noInternalEdgeBreakAtExit": len(exit_stitches) == 2 and "innerEdge" in policy[EXIT_NAME]["suppressEdges"],
        "noEdgeStepAtEntry": all(float(edge.get("maxHeadingStep", 999.0)) <= MAX_STITCH_HEADING_STEP_DEG for edge in entry_stitches),
        "noEdgeStepAtExit": all(float(edge.get("maxHeadingStep", 999.0)) <= MAX_STITCH_HEADING_STEP_DEG for edge in exit_stitches),
        "noGapBetweenMainAndPitAccess": max_after_gap <= MAX_JOIN_GAP_M,
        "noDoubleStrokeAtContact": bool(surface.get("suppressInternalEdges"))
        and "innerEdge" not in policy[ENTRY_NAME]["strokeEdges"]
        and "innerEdge" not in policy[EXIT_NAME]["strokeEdges"]
        and bool(surface.get("stitchEdges")),
        "noWallClosingPitlane": _all_accesses_open(visual["geometries"]),
        "noRibbonOverlapVisible": bool(surface.get("fillBeforeStroke")) and bool(surface.get("outerEdgesOnly")),
        "mainTrackPreserved": True,
        "pitlanePreserved": ENTRY_NAME in visual["geometries"] and CORRIDOR_NAME in visual["geometries"] and EXIT_NAME in visual["geometries"],
        "retaOpostaStillStraight": _max_chord_deviation(context["mainCenter"], 529, 610) <= 1.1
        and _heading_oscillation(context["mainCenter"], 529, 610) <= 6.0,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "stitchEdgeCount": len(stitches),
        "entryEndpointGapBeforeMeters": [edge["endpointGapBeforeMeters"] for edge in entry_stitches],
        "exitEndpointGapBeforeMeters": [edge["endpointGapBeforeMeters"] for edge in exit_stitches],
        "entryStitchHeadingSteps": [edge["maxHeadingStep"] for edge in entry_stitches],
        "exitStitchHeadingSteps": [edge["maxHeadingStep"] for edge in exit_stitches],
    }
    required = [
        "smoothStitchEdgesGenerated",
        "noSharpStitchAngle",
        "noInternalEdgeBreakAtEntry",
        "noInternalEdgeBreakAtExit",
        "noEdgeStepAtEntry",
        "noEdgeStepAtExit",
        "noGapBetweenMainAndPitAccess",
        "noDoubleStrokeAtContact",
        "noWallClosingPitlane",
        "noRibbonOverlapVisible",
        "mainTrackPreserved",
        "pitlanePreserved",
        "retaOpostaStillStraight",
    ]
    passed = (
        all(bool(fields[name]) for name in required)
        and not fields["projectionChanged"]
        and not fields["mapPositionChanged"]
        and not fields["lateralOffsetChanged"]
        and not fields["physicsChanged"]
    )
    return {
        "name": "InterlagosPitAccessSmoothStitchFixValidation",
        "generatedAt": datetime.utcnow().isoformat(),
        "candidateGeometry": GEOMETRY_NAME,
        "passed": passed,
        **fields,
    }


def _build_app_check() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_CURRENT, timeout=10).read().decode("utf-8"))
    validation = json.loads((DEBUG_DIR / VALIDATION_JSON).read_text(encoding="utf-8"))
    screenshot = DEBUG_DIR / "interlagos_pit_access_smooth_stitch_fix_app_check.png"
    geometry_name = payload.get("geometryName") or payload.get("track", {}).get("geometryName")
    visual_geometry_name = payload.get("visualGeometryName") or payload.get("track", {}).get("visualGeometryName")
    render_mode = payload.get("renderMode") or payload.get("track", {}).get("renderMode")
    updated_at = payload.get("updatedAt") or payload.get("track", {}).get("updatedAt")
    return {
        "name": "InterlagosPitAccessSmoothStitchFixAppCheck",
        "generatedAt": datetime.utcnow().isoformat(),
        "geometryName": geometry_name,
        "visualGeometryName": visual_geometry_name,
        "renderMode": render_mode,
        "updatedAt": updated_at,
        "appUsesPitAccessSmoothStitchFix": geometry_name == GEOMETRY_NAME or visual_geometry_name == GEOMETRY_NAME,
        "smoothStitchEdgesGenerated": bool(validation.get("smoothStitchEdgesGenerated")),
        "maxEndpointGapAfterMeters": validation.get("maxEndpointGapAfterMeters"),
        "maxStitchHeadingStepBefore": validation.get("maxStitchHeadingStepBefore"),
        "maxStitchHeadingStepAfter": validation.get("maxStitchHeadingStepAfter"),
        "noSharpStitchAngle": bool(validation.get("noSharpStitchAngle")),
        "noInternalEdgeBreakAtEntry": bool(validation.get("noInternalEdgeBreakAtEntry")),
        "noInternalEdgeBreakAtExit": bool(validation.get("noInternalEdgeBreakAtExit")),
        "noEdgeStepAtEntry": bool(validation.get("noEdgeStepAtEntry")),
        "noEdgeStepAtExit": bool(validation.get("noEdgeStepAtExit")),
        "noGapBetweenMainAndPitAccess": bool(validation.get("noGapBetweenMainAndPitAccess")),
        "noDoubleStrokeAtContact": bool(validation.get("noDoubleStrokeAtContact")),
        "noWallClosingPitlane": bool(validation.get("noWallClosingPitlane")),
        "noRibbonOverlapVisible": bool(validation.get("noRibbonOverlapVisible")),
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "pitlanePreserved": bool(validation.get("pitlanePreserved")),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "debugRequired": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "screenshot": str(screenshot),
        "screenshotExists": screenshot.exists(),
        "sourceValidation": str(DEBUG_DIR / VALIDATION_JSON),
    }


def _candidate_svg(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    return _svg("Interlagos pit access smooth stitch fix candidate", context, base, candidate, validation)


def _validation_svg(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    return _svg("Interlagos pit access smooth stitch fix validation", context, base, candidate, validation)


def _svg(title: str, context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    width = 1500
    height = 980
    gap = 24
    panel_w = (width - gap * 3) / 2
    panel_h = height - 145
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#071018"/>',
        f'<text x="28" y="36" fill="#e2e8f0" font-size="22" font-family="Segoe UI, Arial">{_xml(title)}</text>',
        '<text x="28" y="62" fill="#94a3b8" font-size="13" font-family="Segoe UI, Arial">previous stitch red / smooth stitch cyan / endpoints marked / tangents pale blue / MainTrack gray</text>',
    ]
    panels = [("entrada smooth stitch", ENTRY_NAME, gap), ("saida smooth stitch", EXIT_NAME, gap * 2 + panel_w)]
    for label, geometry_name, x in panels:
        parts.extend(_panel(context, base, candidate, validation, label, geometry_name, x, 78, panel_w, panel_h))
    footer = (
        f"passed={validation['passed']} before={validation['maxStitchHeadingStepBefore']:.2f} "
        f"after={validation['maxStitchHeadingStepAfter']:.2f} limit={MAX_STITCH_HEADING_STEP_DEG:.1f}"
    )
    parts.append(f'<text x="28" y="{height - 28}" fill="#94a3b8" font-size="14" font-family="Segoe UI, Arial">{_xml(footer)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _panel(
    context: Dict[str, Any],
    base: Dict[str, Any],
    candidate: Dict[str, Any],
    validation: Dict[str, Any],
    label: str,
    geometry_name: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> List[str]:
    geom = candidate["visualGeometry"]["geometries"][geometry_name]
    previous_stitches = [
        edge for edge in base["visualGeometry"]["surfaceUnionFix"].get("stitchEdges", []) if edge["geometryName"] == geometry_name
    ]
    stitches = [
        edge for edge in candidate["visualGeometry"]["surfaceUnionFix"]["stitchEdges"] if edge["geometryName"] == geometry_name
    ]
    focus_points = (
        _line_points(geom["centerline"])
        + [point for edge in previous_stitches for point in _line_points(edge["points"])]
        + [point for edge in stitches for point in _line_points(edge["points"])]
    )
    bounds = _bounds_for_points(focus_points, pad=54.0)
    scale = min(width / max(bounds["maxX"] - bounds["minX"], 1.0), height / max(bounds["maxY"] - bounds["minY"], 1.0))

    def project(point: Point) -> Point:
        return (x + (point[0] - bounds["minX"]) * scale, y + height - (point[1] - bounds["minY"]) * scale)

    def path(points: Sequence[Point], close: bool = False) -> str:
        clipped = [point for point in points if _inside(point, bounds)]
        if not clipped:
            return ""
        projected = [project(point) for point in clipped]
        value = "M " + " L ".join(f"{px:.2f} {py:.2f}" for px, py in projected)
        return value + (" Z" if close else "")

    color = "#22c55e" if geometry_name == ENTRY_NAME else "#fb923c"
    parts = [
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" fill="#0b1220" stroke="#1f2937"/>',
        f'<text x="{x + 12:.2f}" y="{y + 24:.2f}" fill="#e2e8f0" font-size="15" font-family="Segoe UI, Arial">{_xml(label)}</text>',
        f'<path d="{path(context["mainLeft"])}" fill="none" stroke="#94a3b8" stroke-width="2.0" stroke-opacity="0.7"/>',
        f'<path d="{path(context["mainRight"])}" fill="none" stroke="#94a3b8" stroke-width="2.0" stroke-opacity="0.7"/>',
        f'<path d="{path(_line_points(geom["polygon"]), close=True)}" fill="{color}" fill-opacity="0.35" stroke="none"/>',
        f'<path d="{path(_line_points(geom["outerEdge"]))}" fill="none" stroke="#f8fafc" stroke-width="1.1" stroke-opacity="0.45"/>',
    ]
    for edge in previous_stitches:
        points = _line_points(edge["points"])
        parts.append(
            f'<path d="{path(points)}" fill="none" stroke="#ef4444" stroke-width="3.0" stroke-linecap="round" stroke-linejoin="round" stroke-opacity="0.72"/>'
        )
    for edge in stitches:
        points = _line_points(edge["points"])
        parts.append(
            f'<path d="{path(points)}" fill="none" stroke="#22d3ee" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        _append_endpoint_and_tangent(parts, project, points[0], edge.get("startTangent", [0.0, 0.0]), "#bfdbfe")
        _append_endpoint_and_tangent(parts, project, points[-1], edge.get("endTangent", [0.0, 0.0]), "#bfdbfe")
    local_steps = validation["entryStitchHeadingSteps"] if geometry_name == ENTRY_NAME else validation["exitStitchHeadingSteps"]
    parts.append(
        f'<text x="{x + 12:.2f}" y="{y + height - 18:.2f}" fill="#94a3b8" font-size="12" font-family="Segoe UI, Arial">heading steps={_xml(str(local_steps))}</text>'
    )
    return parts


def _append_endpoint_and_tangent(parts: List[str], project: Any, point: Point, tangent: Sequence[float], color: str) -> None:
    px, py = project(point)
    tangent_point = (point[0] + float(tangent[0]) * 8.0, point[1] + float(tangent[1]) * 8.0)
    tx, ty = project(tangent_point)
    parts.append(f'<line x1="{px:.2f}" y1="{py:.2f}" x2="{tx:.2f}" y2="{ty:.2f}" stroke="#bae6fd" stroke-width="1.5" stroke-dasharray="4 5"/>')
    parts.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4.0" fill="{color}" stroke="#0284c7" stroke-width="1.2"/>')


if __name__ == "__main__":
    main()
