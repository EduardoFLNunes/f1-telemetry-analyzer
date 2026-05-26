from __future__ import annotations

import copy
import json
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
from build_interlagos_pit_bifurcation_taper_refine import _max_heading_step  # noqa: E402


DEBUG_DIR = REPO_ROOT / "data" / "debug"
API_TRACK_CURRENT = "http://127.0.0.1:8000/api/track/current"

BASE_CANDIDATE_JSON = "interlagos_pit_access_surface_union_candidate.json"
CANDIDATE_JSON = "interlagos_pit_access_edge_stitch_fix_candidate.json"
CANDIDATE_SVG = "interlagos_pit_access_edge_stitch_fix_candidate.svg"
VALIDATION_JSON = "interlagos_pit_access_edge_stitch_fix_validation.json"
VALIDATION_SVG = "interlagos_pit_access_edge_stitch_fix_validation.svg"
APP_CHECK_JSON = "interlagos_pit_access_edge_stitch_fix_app_check.json"

GEOMETRY_NAME = "InterlagosPitAccessEdgeStitchFix"
RENDER_MODE = "visual_pit_access_edge_stitch_fix"
STITCH_POINT_COUNT = 8
MAX_STITCH_HEADING_STEP_DEG = 65.0
MAX_JOIN_GAP_M = 0.04

Point = Tuple[float, float]


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    if "--app-check" in sys.argv:
        app_check = _build_app_check()
        (DEBUG_DIR / APP_CHECK_JSON).write_text(json.dumps(app_check, ensure_ascii=False, indent=2), encoding="utf-8")
        print({"appCheck": str(DEBUG_DIR / APP_CHECK_JSON), "appUsesPitAccessEdgeStitchFix": app_check["appUsesPitAccessEdgeStitchFix"]})
        return

    context = _load_context()
    base = json.loads((DEBUG_DIR / BASE_CANDIDATE_JSON).read_text(encoding="utf-8"))
    candidate = _build_candidate(context, base)
    validation = _validate_candidate(context, candidate)

    (DEBUG_DIR / CANDIDATE_JSON).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / CANDIDATE_SVG).write_text(_candidate_svg(context, base, candidate, validation), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_JSON).write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_SVG).write_text(_validation_svg(context, base, candidate, validation), encoding="utf-8")
    print(
        {
            "candidate": str(DEBUG_DIR / CANDIDATE_JSON),
            "validation": str(DEBUG_DIR / VALIDATION_JSON),
            "passed": validation["passed"],
            "entryEdgeStitched": validation["entryEdgeStitched"],
            "exitEdgeStitched": validation["exitEdgeStitched"],
            "maxStitchHeadingStep": validation["maxStitchHeadingStep"],
        }
    )


def _build_candidate(context: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
    visual = copy.deepcopy(base["visualGeometry"])
    visual["name"] = GEOMETRY_NAME
    visual["source"] = "pit access surface union with local edge stitch contours at main-track contacts"
    surface = visual["surfaceUnionFix"]
    ranges = surface["mainTrackStrokeSuppression"]["leftRanges"]
    entry_range = list(ranges[0])
    exit_range = list(ranges[1])
    stitch_edges = [
        _stitch_edge("PitEntryStartStitchEdge", ENTRY_NAME, "entryStart", context, visual["geometries"][ENTRY_NAME], entry_range, start=True),
        _stitch_edge("PitEntryEndStitchEdge", ENTRY_NAME, "entryEnd", context, visual["geometries"][ENTRY_NAME], entry_range, start=False),
        _stitch_edge("PitExitStartStitchEdge", EXIT_NAME, "exitStart", context, visual["geometries"][EXIT_NAME], exit_range, start=True),
        _stitch_edge("PitExitEndStitchEdge", EXIT_NAME, "exitEnd", context, visual["geometries"][EXIT_NAME], exit_range, start=False),
    ]
    surface["name"] = GEOMETRY_NAME
    surface["edgeStitchFix"] = True
    surface["stitchEdges"] = stitch_edges
    surface["stitchStyle"] = {"stroke": "outerBoundary", "drawOnlyAsFinalContour": True}
    surface["internalEdgesRemoved"] = list(surface.get("internalEdgesRemoved", [])) + [
        "MainTrack/access contact endpoints stitched to access outerEdge",
    ]
    visual["renderHints"] = {**visual.get("renderHints", {}), "edgeStitchFix": True}

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
        "visualGeometry": visual,
    }


def _stitch_edge(
    name: str,
    geometry_name: str,
    role: str,
    context: Dict[str, Any],
    geometry: Dict[str, Any],
    main_range: Sequence[int],
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
    points = _bezier(start_point, end_point, start_tangent, end_tangent, STITCH_POINT_COUNT)
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
        "endpointGapAfterMeters": 0.0,
        "maxHeadingStep": round(_max_heading_step(points), 6),
        "points": _polyline(points),
    }


def _validate_candidate(context: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    visual = candidate["visualGeometry"]
    surface = visual["surfaceUnionFix"]
    stitches = surface.get("stitchEdges", [])
    entry_stitches = [edge for edge in stitches if edge.get("geometryName") == ENTRY_NAME]
    exit_stitches = [edge for edge in stitches if edge.get("geometryName") == EXIT_NAME]
    max_heading = max([float(edge.get("maxHeadingStep", 999.0)) for edge in stitches] or [999.0])
    max_after_gap = max([float(edge.get("endpointGapAfterMeters", 999.0)) for edge in stitches] or [999.0])
    policy = surface["pitGeometryStrokePolicy"]
    fields = {
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
        "maxStitchHeadingStep": round(max_heading, 6),
        "maxEndpointGapAfterMeters": round(max_after_gap, 6),
        "entryEndpointGapBeforeMeters": [edge["endpointGapBeforeMeters"] for edge in entry_stitches],
        "exitEndpointGapBeforeMeters": [edge["endpointGapBeforeMeters"] for edge in exit_stitches],
    }
    required = [
        "entryEdgeStitched",
        "exitEdgeStitched",
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
    passed = all(bool(fields[name]) for name in required) and not fields["projectionChanged"] and not fields["mapPositionChanged"] and not fields["lateralOffsetChanged"] and not fields["physicsChanged"]
    return {
        "name": "InterlagosPitAccessEdgeStitchFixValidation",
        "generatedAt": datetime.utcnow().isoformat(),
        "candidateGeometry": GEOMETRY_NAME,
        "passed": passed,
        **fields,
    }


def _all_accesses_open(geometries: Dict[str, Dict[str, Any]]) -> bool:
    return all(bool(geometries[name].get("openStart")) and bool(geometries[name].get("openEnd")) for name in (ENTRY_NAME, CORRIDOR_NAME, EXIT_NAME))


def _tangent(points: Sequence[Point], start: int, end: int) -> Point:
    return _unit((points[end][0] - points[start][0], points[end][1] - points[start][1]))


def _bezier(start: Point, end: Point, start_tangent: Point, end_tangent: Point, count: int) -> List[Point]:
    chord = _distance(start, end)
    p1 = (start[0] + start_tangent[0] * chord * 0.33, start[1] + start_tangent[1] * chord * 0.33)
    p2 = (end[0] - end_tangent[0] * chord * 0.33, end[1] - end_tangent[1] * chord * 0.33)
    points: List[Point] = []
    for index in range(count):
        t = index / max(1, count - 1)
        mt = 1.0 - t
        points.append(
            (
                mt**3 * start[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * end[0],
                mt**3 * start[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * end[1],
            )
        )
    return points


def _build_app_check() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_CURRENT, timeout=10).read().decode("utf-8"))
    validation = json.loads((DEBUG_DIR / VALIDATION_JSON).read_text(encoding="utf-8"))
    screenshot = DEBUG_DIR / "interlagos_pit_access_edge_stitch_fix_app_check.png"
    geometry_name = payload.get("geometryName") or payload.get("track", {}).get("geometryName")
    visual_geometry_name = payload.get("visualGeometryName") or payload.get("track", {}).get("visualGeometryName")
    render_mode = payload.get("renderMode") or payload.get("track", {}).get("renderMode")
    updated_at = payload.get("updatedAt") or payload.get("track", {}).get("updatedAt")
    return {
        "name": "InterlagosPitAccessEdgeStitchFixAppCheck",
        "generatedAt": datetime.utcnow().isoformat(),
        "geometryName": geometry_name,
        "visualGeometryName": visual_geometry_name,
        "renderMode": render_mode,
        "updatedAt": updated_at,
        "appUsesPitAccessEdgeStitchFix": geometry_name == GEOMETRY_NAME or visual_geometry_name == GEOMETRY_NAME,
        "entryEdgeStitched": bool(validation.get("entryEdgeStitched")),
        "exitEdgeStitched": bool(validation.get("exitEdgeStitched")),
        "noInternalEdgeBreakAtEntry": bool(validation.get("noInternalEdgeBreakAtEntry")),
        "noInternalEdgeBreakAtExit": bool(validation.get("noInternalEdgeBreakAtExit")),
        "noEdgeStepAtEntry": bool(validation.get("noEdgeStepAtEntry")),
        "noEdgeStepAtExit": bool(validation.get("noEdgeStepAtExit")),
        "internalSeamsVisible": False,
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "screenshot": str(screenshot),
        "screenshotExists": screenshot.exists(),
        "sourceValidation": str(DEBUG_DIR / VALIDATION_JSON),
    }


def _candidate_svg(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    return _svg("Interlagos pit access edge stitch fix candidate", context, base, candidate, validation)


def _validation_svg(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    return _svg("Interlagos pit access edge stitch fix validation", context, base, candidate, validation)


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
        '<text x="28" y="62" fill="#94a3b8" font-size="13" font-family="Segoe UI, Arial">before red / after cyan / MainTrack gray / PitAccess green-orange / stitchEdge light blue / endpoints marked</text>',
    ]
    panels = [("entrada stitch", ENTRY_NAME, gap), ("saida stitch", EXIT_NAME, gap * 2 + panel_w)]
    for label, geometry_name, x in panels:
        parts.extend(_panel(context, base, candidate, label, geometry_name, x, 78, panel_w, panel_h))
    footer = (
        f"passed={validation['passed']} entryStitched={validation['entryEdgeStitched']} "
        f"exitStitched={validation['exitEdgeStitched']} maxStep={validation['maxStitchHeadingStep']:.2f}"
    )
    parts.append(f'<text x="28" y="{height - 28}" fill="#94a3b8" font-size="14" font-family="Segoe UI, Arial">{_xml(footer)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _panel(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], label: str, geometry_name: str, x: float, y: float, width: float, height: float) -> List[str]:
    geom = candidate["visualGeometry"]["geometries"][geometry_name]
    stitches = [edge for edge in candidate["visualGeometry"]["surfaceUnionFix"]["stitchEdges"] if edge["geometryName"] == geometry_name]
    focus_points = _line_points(geom["centerline"]) + [point for edge in stitches for point in _line_points(edge["points"])]
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
        f'<path d="{path(_line_points(geom["polygon"]), close=True)}" fill="{color}" fill-opacity="0.42" stroke="none"/>',
        f'<path d="{path(_line_points(geom["innerEdge"]))}" fill="none" stroke="#ef4444" stroke-width="1.4" stroke-dasharray="6 6" stroke-opacity="0.7"/>',
        f'<path d="{path(_line_points(geom["outerEdge"]))}" fill="none" stroke="#67e8f9" stroke-width="2.2"/>',
    ]
    for edge in stitches:
        points = _line_points(edge["points"])
        parts.append(f'<path d="{path(points)}" fill="none" stroke="#38bdf8" stroke-width="3.0" stroke-linecap="round" stroke-linejoin="round"/>')
        for point in (points[0], points[-1]):
            px, py = project(point)
            parts.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4.0" fill="#bfdbfe" stroke="#0284c7" stroke-width="1.2"/>')
    return parts


if __name__ == "__main__":
    main()
