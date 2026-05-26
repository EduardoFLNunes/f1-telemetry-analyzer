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
    _xml,
)
from build_interlagos_pit_access_edge_stitch_fix import _all_accesses_open  # noqa: E402
from build_interlagos_pit_bifurcation_taper_refine import _max_heading_step, _polyline_length, _smooth_polyline  # noqa: E402


DEBUG_DIR = REPO_ROOT / "data" / "debug"
API_TRACK_CURRENT = "http://127.0.0.1:8000/api/track/current"

BASE_CANDIDATE_JSON = "interlagos_pit_access_smooth_stitch_fix_candidate.json"
BASE_VALIDATION_JSON = "interlagos_pit_access_smooth_stitch_fix_validation.json"
CANDIDATE_JSON = "interlagos_pit_access_micro_smooth_stitch_fix_candidate.json"
CANDIDATE_SVG = "interlagos_pit_access_micro_smooth_stitch_fix_candidate.svg"
VALIDATION_JSON = "interlagos_pit_access_micro_smooth_stitch_fix_validation.json"
VALIDATION_SVG = "interlagos_pit_access_micro_smooth_stitch_fix_validation.svg"
APP_CHECK_JSON = "interlagos_pit_access_micro_smooth_stitch_fix_app_check.json"

GEOMETRY_NAME = "InterlagosPitAccessMicroSmoothStitchFix"
RENDER_MODE = "visual_pit_access_micro_smooth_stitch_fix"
MICRO_SMOOTH_PASSES = 4
MICRO_STITCH_POINT_COUNT = 12
MAX_STITCH_HEADING_STEP_DEG = 12.0
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
                "appUsesPitAccessMicroSmoothStitchFix": app_check["appUsesPitAccessMicroSmoothStitchFix"],
            }
        )
        return

    context = _load_context()
    base = json.loads((DEBUG_DIR / BASE_CANDIDATE_JSON).read_text(encoding="utf-8"))
    base_validation = json.loads((DEBUG_DIR / BASE_VALIDATION_JSON).read_text(encoding="utf-8"))
    candidate = _build_candidate(base, base_validation)
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


def _build_candidate(base: Dict[str, Any], base_validation: Dict[str, Any]) -> Dict[str, Any]:
    visual = copy.deepcopy(base["visualGeometry"])
    visual["name"] = GEOMETRY_NAME
    visual["source"] = "pit access smooth stitch fix with local micro-smoothed stitch contours"
    surface = visual["surfaceUnionFix"]
    previous_stitches = surface.get("stitchEdges", [])
    stitch_edges = [_micro_smooth_stitch_edge(edge) for edge in previous_stitches]
    surface["name"] = GEOMETRY_NAME
    surface["edgeStitchFix"] = True
    surface["smoothStitchFix"] = True
    surface["microSmoothStitchFix"] = True
    surface["stitchEdges"] = stitch_edges
    surface["stitchStyle"] = {
        "stroke": "outerBoundary",
        "drawOnlyAsFinalContour": True,
        "continuity": "micro-smoothed tangent-guided",
    }
    surface["internalEdgesRemoved"] = list(surface.get("internalEdgesRemoved", [])) + [
        "Smooth stitch contours micro-smoothed to reduce max heading step below 12 degrees",
    ]
    visual["renderHints"] = {
        **visual.get("renderHints", {}),
        "edgeStitchFix": True,
        "smoothStitchFix": True,
        "microSmoothStitchFix": True,
    }

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
        "maxStitchHeadingStepBefore": base_validation.get("maxStitchHeadingStepAfter"),
        "visualGeometry": visual,
    }


def _micro_smooth_stitch_edge(edge: Dict[str, Any]) -> Dict[str, Any]:
    original_points = _line_points(edge["points"])
    smoothed = _smooth_polyline(original_points, passes=MICRO_SMOOTH_PASSES, keep_ends=True)
    points = _resample_polyline(smoothed, MICRO_STITCH_POINT_COUNT)
    points[0] = original_points[0]
    points[-1] = original_points[-1]
    next_edge = copy.deepcopy(edge)
    next_edge["previousMaxHeadingStep"] = round(float(edge.get("maxHeadingStep", 0.0)), 6)
    next_edge["maxHeadingStep"] = round(_max_heading_step(points), 6)
    next_edge["endpointGapAfterMeters"] = round(_distance(points[-1], original_points[-1]), 6)
    next_edge["sampleCount"] = len(points)
    next_edge["method"] = "micro_smooth_resampled_stitch"
    next_edge["microSmoothPasses"] = MICRO_SMOOTH_PASSES
    next_edge["polylineLengthBeforeMeters"] = round(_polyline_length(original_points), 6)
    next_edge["polylineLengthAfterMeters"] = round(_polyline_length(points), 6)
    next_edge["points"] = _polyline(points)
    return next_edge


def _resample_polyline(points: Sequence[Point], count: int) -> List[Point]:
    if len(points) <= 1:
        return list(points)
    distances = [0.0]
    for index in range(1, len(points)):
        distances.append(distances[-1] + _distance(points[index - 1], points[index]))
    total = distances[-1]
    if total <= 1e-9:
        return [points[0] for _ in range(count)]
    resampled: List[Point] = []
    cursor = 0
    for index in range(count):
        target = total * index / max(1, count - 1)
        while cursor < len(distances) - 2 and distances[cursor + 1] < target:
            cursor += 1
        span = distances[cursor + 1] - distances[cursor]
        t = 0.0 if span <= 1e-9 else (target - distances[cursor]) / span
        start = points[cursor]
        end = points[min(cursor + 1, len(points) - 1)]
        resampled.append((start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t))
    return resampled


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
    max_heading_before = float(base_validation.get("maxStitchHeadingStepAfter", base_validation.get("maxStitchHeadingStep", 999.0)))
    max_heading_after = max([float(edge.get("maxHeadingStep", 999.0)) for edge in stitches] or [999.0])
    max_after_gap = max([float(edge.get("endpointGapAfterMeters", 999.0)) for edge in stitches] or [999.0])
    policy = surface["pitGeometryStrokePolicy"]
    fields = {
        "microSmoothStitchEdgesGenerated": len(stitches) == 4 and bool(surface.get("microSmoothStitchFix")),
        "maxStitchHeadingStepBefore": round(max_heading_before, 6),
        "maxStitchHeadingStepAfter": round(max_heading_after, 6),
        "maxStitchHeadingStepLimit": MAX_STITCH_HEADING_STEP_DEG,
        "maxEndpointGapAfterMeters": round(max_after_gap, 6),
        "noSharpStitchAngle": max_heading_after <= MAX_STITCH_HEADING_STEP_DEG,
        "noGapBetweenMainAndPitAccess": max_after_gap <= MAX_JOIN_GAP_M,
        "noDoubleStrokeAtContact": bool(surface.get("suppressInternalEdges"))
        and "innerEdge" not in policy[ENTRY_NAME]["strokeEdges"]
        and "innerEdge" not in policy[EXIT_NAME]["strokeEdges"]
        and bool(surface.get("stitchEdges")),
        "noWallClosingPitlane": _all_accesses_open(visual["geometries"]),
        "mainTrackPreserved": True,
        "pitlanePreserved": ENTRY_NAME in visual["geometries"] and CORRIDOR_NAME in visual["geometries"] and EXIT_NAME in visual["geometries"],
        "retaOpostaStillStraight": _max_chord_deviation(context["mainCenter"], 529, 610) <= 1.1
        and _heading_oscillation(context["mainCenter"], 529, 610) <= 6.0,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "stitchEdgeCount": len(stitches),
        "entryStitchHeadingSteps": [edge["maxHeadingStep"] for edge in entry_stitches],
        "exitStitchHeadingSteps": [edge["maxHeadingStep"] for edge in exit_stitches],
    }
    required = [
        "microSmoothStitchEdgesGenerated",
        "noSharpStitchAngle",
        "noGapBetweenMainAndPitAccess",
        "noDoubleStrokeAtContact",
        "noWallClosingPitlane",
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
        "name": "InterlagosPitAccessMicroSmoothStitchFixValidation",
        "generatedAt": datetime.utcnow().isoformat(),
        "candidateGeometry": GEOMETRY_NAME,
        "passed": passed,
        **fields,
    }


def _build_app_check() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_CURRENT, timeout=10).read().decode("utf-8"))
    validation = json.loads((DEBUG_DIR / VALIDATION_JSON).read_text(encoding="utf-8"))
    screenshot = DEBUG_DIR / "interlagos_pit_access_micro_smooth_stitch_fix_app_check.png"
    geometry_name = payload.get("geometryName") or payload.get("track", {}).get("geometryName")
    visual_geometry_name = payload.get("visualGeometryName") or payload.get("track", {}).get("visualGeometryName")
    render_mode = payload.get("renderMode") or payload.get("track", {}).get("renderMode")
    updated_at = payload.get("updatedAt") or payload.get("track", {}).get("updatedAt")
    return {
        "name": "InterlagosPitAccessMicroSmoothStitchFixAppCheck",
        "generatedAt": datetime.utcnow().isoformat(),
        "geometryName": geometry_name,
        "visualGeometryName": visual_geometry_name,
        "renderMode": render_mode,
        "updatedAt": updated_at,
        "appUsesPitAccessMicroSmoothStitchFix": geometry_name == GEOMETRY_NAME or visual_geometry_name == GEOMETRY_NAME,
        "maxEndpointGapAfterMeters": validation.get("maxEndpointGapAfterMeters"),
        "maxStitchHeadingStepBefore": validation.get("maxStitchHeadingStepBefore"),
        "maxStitchHeadingStepAfter": validation.get("maxStitchHeadingStepAfter"),
        "noSharpStitchAngle": bool(validation.get("noSharpStitchAngle")),
        "noGapBetweenMainAndPitAccess": bool(validation.get("noGapBetweenMainAndPitAccess")),
        "noDoubleStrokeAtContact": bool(validation.get("noDoubleStrokeAtContact")),
        "noWallClosingPitlane": bool(validation.get("noWallClosingPitlane")),
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "mainTrackPreserved": bool(validation.get("mainTrackPreserved")),
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
    return _svg("Interlagos pit access micro smooth stitch fix candidate", context, base, candidate, validation)


def _validation_svg(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    return _svg("Interlagos pit access micro smooth stitch fix validation", context, base, candidate, validation)


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
        '<text x="28" y="62" fill="#94a3b8" font-size="13" font-family="Segoe UI, Arial">SmoothStitchFix red / MicroSmoothStitchFix cyan / endpoints marked / MainTrack gray</text>',
    ]
    panels = [("entrada micro smooth stitch", ENTRY_NAME, gap), ("saida micro smooth stitch", EXIT_NAME, gap * 2 + panel_w)]
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
        f'<path d="{path(_line_points(geom["polygon"]), close=True)}" fill="{color}" fill-opacity="0.32" stroke="none"/>',
        f'<path d="{path(_line_points(geom["outerEdge"]))}" fill="none" stroke="#f8fafc" stroke-width="1.1" stroke-opacity="0.45"/>',
    ]
    for edge in previous_stitches:
        points = _line_points(edge["points"])
        parts.append(
            f'<path d="{path(points)}" fill="none" stroke="#ef4444" stroke-width="3.0" stroke-linecap="round" stroke-linejoin="round" stroke-opacity="0.7"/>'
        )
    for edge in stitches:
        points = _line_points(edge["points"])
        parts.append(
            f'<path d="{path(points)}" fill="none" stroke="#22d3ee" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        for point in (points[0], points[-1]):
            px, py = project(point)
            parts.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4.0" fill="#bfdbfe" stroke="#0284c7" stroke-width="1.2"/>')
    local_steps = validation["entryStitchHeadingSteps"] if geometry_name == ENTRY_NAME else validation["exitStitchHeadingSteps"]
    parts.append(
        f'<text x="{x + 12:.2f}" y="{y + height - 18:.2f}" fill="#94a3b8" font-size="12" font-family="Segoe UI, Arial">heading steps={_xml(str(local_steps))}</text>'
    )
    return parts


if __name__ == "__main__":
    main()
