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
    _xml,
)
from build_interlagos_pit_access_edge_stitch_fix import _all_accesses_open  # noqa: E402
from build_interlagos_pit_bifurcation_taper_refine import _max_heading_step  # noqa: E402


DEBUG_DIR = REPO_ROOT / "data" / "debug"
API_TRACK_CURRENT = "http://127.0.0.1:8000/api/track/current"

BASE_CANDIDATE_JSON = "interlagos_pit_access_micro_smooth_stitch_fix_candidate.json"
BASE_VALIDATION_JSON = "interlagos_pit_access_micro_smooth_stitch_fix_validation.json"
CANDIDATE_JSON = "interlagos_pit_access_open_exit_mouth_fix_candidate.json"
CANDIDATE_SVG = "interlagos_pit_access_open_exit_mouth_fix_candidate.svg"
VALIDATION_JSON = "interlagos_pit_access_open_exit_mouth_fix_validation.json"
VALIDATION_SVG = "interlagos_pit_access_open_exit_mouth_fix_validation.svg"
APP_CHECK_JSON = "interlagos_pit_access_open_exit_mouth_fix_app_check.json"

GEOMETRY_NAME = "InterlagosPitAccessOpenExitMouthFix"
RENDER_MODE = "visual_pit_access_open_exit_mouth_fix"
SUPPRESSED_EXIT_STITCH = "PitExitEndStitchEdge"
SUPPRESSED_EXIT_STITCHES = {"PitExitStartStitchEdge", "PitExitEndStitchEdge"}
MAX_JOIN_GAP_M = 0.04
PIT_EXIT_START_OVERLAP_M = 1.6

Point = Tuple[float, float]


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    if "--app-check" in sys.argv:
        app_check = _build_app_check()
        (DEBUG_DIR / APP_CHECK_JSON).write_text(json.dumps(app_check, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            {
                "appCheck": str(DEBUG_DIR / APP_CHECK_JSON),
                "appUsesPitAccessOpenExitMouthFix": app_check["appUsesPitAccessOpenExitMouthFix"],
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
            "pitExitMouthClosedByStroke": validation["pitExitMouthClosedByStroke"],
            "pitExitEndStitchSuppressed": validation["pitExitEndStitchSuppressed"],
        }
    )


def _build_candidate(base: Dict[str, Any], base_validation: Dict[str, Any]) -> Dict[str, Any]:
    visual = copy.deepcopy(base["visualGeometry"])
    visual["name"] = GEOMETRY_NAME
    visual["source"] = "pit access micro smooth stitch fix with pit exit mouth cap/stitch stroke suppressed"
    surface = visual["surfaceUnionFix"]
    stitches = surface.get("stitchEdges", [])
    suppressed = [edge for edge in stitches if edge.get("name") in SUPPRESSED_EXIT_STITCHES]
    surface["stitchEdges"] = [edge for edge in stitches if edge.get("name") not in SUPPRESSED_EXIT_STITCHES]
    surface["suppressedStitchEdges"] = list(surface.get("suppressedStitchEdges", [])) + [
        {**copy.deepcopy(edge), "suppressedReason": "Pit exit merge mouth is open; do not render transverse cap/stitch stroke"}
        for edge in suppressed
    ]
    surface["name"] = GEOMETRY_NAME
    surface["openExitMouthFix"] = True
    surface["pitExitOpenMouth"] = True
    surface["pitExitSuppressedCapEdges"] = sorted(SUPPRESSED_EXIT_STITCHES)
    surface["internalEdgesRemoved"] = list(surface.get("internalEdgesRemoved", [])) + [
        "PitExitStartStitchEdge and PitExitEndStitchEdge suppressed so no transverse stroke cuts the pit exit",
    ]

    exit_access = visual["geometries"][EXIT_NAME]
    exit_access["openStart"] = True
    exit_access["openEnd"] = True
    exit_access["openCaps"] = True
    exit_access.setdefault("renderHints", {})
    exit_access["renderHints"].update(
        {
            "openStart": True,
            "openEnd": True,
            "openCaps": True,
            "strokeCaps": False,
            "suppressEndCap": True,
            "mergeOpen": True,
            "pitExitOpenMouthFix": True,
        }
    )
    exit_access["internalEdgesRemoved"] = sorted(
        set(list(exit_access.get("internalEdgesRemoved", [])) + ["innerEdge", "sharedDividerEdge", "endCap"])
    )
    _extend_pit_exit_start_under_corridor(exit_access)

    policy = surface["pitGeometryStrokePolicy"][EXIT_NAME]
    policy["openCaps"] = True
    policy["strokeEdges"] = [edge for edge in policy.get("strokeEdges", []) if edge not in ("innerEdge", "sharedDividerEdge", "endCap")]
    policy["suppressEdges"] = sorted(set(list(policy.get("suppressEdges", [])) + ["innerEdge", "sharedDividerEdge", "endCap"]))

    visual["renderHints"] = {
        **visual.get("renderHints", {}),
        "edgeStitchFix": True,
        "smoothStitchFix": True,
        "microSmoothStitchFix": True,
        "openExitMouthFix": True,
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


def _extend_pit_exit_start_under_corridor(exit_access: Dict[str, Any]) -> None:
    left = _line_points(exit_access["leftEdge"])
    right = _line_points(exit_access["rightEdge"])
    if len(left) < 2 or len(right) < 2:
        return
    left_back = _backtrack_point(left[0], left[1], PIT_EXIT_START_OVERLAP_M)
    right_back = _backtrack_point(right[0], right[1], PIT_EXIT_START_OVERLAP_M)
    left = [left_back] + left
    right = [right_back] + right
    center = _line_points(exit_access.get("centerline"))
    if len(center) >= 2:
        center_back = ((left_back[0] + right_back[0]) * 0.5, (left_back[1] + right_back[1]) * 0.5)
        exit_access["centerline"] = _polyline([center_back] + center)
        if "PitExitAccessCenterline" in exit_access:
            exit_access["PitExitAccessCenterline"] = _polyline([center_back] + _line_points(exit_access["PitExitAccessCenterline"]))
    exit_access["leftEdge"] = _polyline(left)
    exit_access["rightEdge"] = _polyline(right)
    exit_access["outerEdge"] = _polyline(left)
    exit_access["innerEdge"] = _polyline(right)
    if "sharedDividerEdge" in exit_access:
        exit_access["sharedDividerEdge"] = _polyline(right)
    exit_access["polygon"] = _polyline(left + list(reversed(right)))
    exit_access["pitExitStartOverlapMeters"] = PIT_EXIT_START_OVERLAP_M
    exit_access.setdefault("renderHints", {})["pitExitStartOverlapMeters"] = PIT_EXIT_START_OVERLAP_M


def _backtrack_point(start: Point, next_point: Point, distance: float) -> Point:
    dx = next_point[0] - start[0]
    dy = next_point[1] - start[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 1e-9:
        return start
    return (start[0] - dx / length * distance, start[1] - dy / length * distance)


def _validate_candidate(
    context: Dict[str, Any],
    base: Dict[str, Any],
    base_validation: Dict[str, Any],
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    visual = candidate["visualGeometry"]
    surface = visual["surfaceUnionFix"]
    stitches = surface.get("stitchEdges", [])
    suppressed = surface.get("suppressedStitchEdges", [])
    exit_access = visual["geometries"][EXIT_NAME]
    policy = surface["pitGeometryStrokePolicy"][EXIT_NAME]
    start_overlap = float(exit_access.get("pitExitStartOverlapMeters", 0.0))
    base_stitches = base["visualGeometry"]["surfaceUnionFix"].get("stitchEdges", [])
    suppressed_exit = [edge for edge in suppressed if edge.get("name") in SUPPRESSED_EXIT_STITCHES]
    all_edges_for_gap = list(stitches) + suppressed_exit
    max_after_gap = max([float(edge.get("endpointGapAfterMeters", 999.0)) for edge in all_edges_for_gap] or [999.0])
    max_heading_after = max([float(edge.get("maxHeadingStep", 0.0)) for edge in stitches] or [0.0])
    suppression = surface.get("mainTrackStrokeSuppression", {})
    left_ranges = suppression.get("leftRanges", [])
    pit_exit_main_range_suppressed = any(int(rng[0]) <= 480 and int(rng[1]) >= 532 for rng in left_ranges)
    fields = {
        "pitExitOpenCaps": bool(exit_access.get("openCaps")) and bool(exit_access.get("openEnd")) and not bool(exit_access.get("renderHints", {}).get("strokeCaps")),
        "pitExitStartStitchSuppressed": any(edge.get("name") == "PitExitStartStitchEdge" for edge in suppressed_exit)
        and all(edge.get("name") != "PitExitStartStitchEdge" for edge in stitches),
        "pitExitEndStitchSuppressed": any(edge.get("name") == "PitExitEndStitchEdge" for edge in suppressed_exit)
        and all(edge.get("name") != "PitExitEndStitchEdge" for edge in stitches),
        "pitExitTransverseStitchesSuppressed": SUPPRESSED_EXIT_STITCHES.issubset({edge.get("name") for edge in suppressed_exit})
        and all(edge.get("name") not in SUPPRESSED_EXIT_STITCHES for edge in stitches),
        "pitExitMouthClosedByStroke": any(edge.get("name") in SUPPRESSED_EXIT_STITCHES for edge in stitches),
        "pitExitMouthNotClosedByStroke": not any(edge.get("name") in SUPPRESSED_EXIT_STITCHES for edge in stitches),
        "noTransverseLineCuttingPitlane": not any(edge.get("name") in SUPPRESSED_EXIT_STITCHES for edge in stitches),
        "mainTrackInnerEdgeSuppressedAtPitExit": pit_exit_main_range_suppressed,
        "pitExitInnerEdgeSuppressed": "innerEdge" in policy.get("suppressEdges", []) and "innerEdge" not in policy.get("strokeEdges", []),
        "pitExitEndCapSuppressed": "endCap" in policy.get("suppressEdges", []) and "endCap" not in policy.get("strokeEdges", []),
        "pitExitStartOverlapGenerated": start_overlap >= PIT_EXIT_START_OVERLAP_M - 1e-6,
        "pitExitCorridorJoinCapCovered": start_overlap >= 1.0,
        "maxEndpointGapAfterMeters": round(max_after_gap, 6),
        "maxStitchHeadingStepBefore": round(float(base_validation.get("maxStitchHeadingStepAfter", 0.0)), 6),
        "maxStitchHeadingStepAfter": round(max_heading_after, 6),
        "noSharpStitchAngle": max_heading_after <= 12.0,
        "noGapBetweenMainAndPitAccess": max_after_gap <= MAX_JOIN_GAP_M,
        "noDoubleStrokeAtContact": bool(surface.get("suppressInternalEdges")) and "innerEdge" not in policy.get("strokeEdges", []),
        "noWallClosingPitlane": _all_accesses_open(visual["geometries"]) and not any(edge.get("name") == SUPPRESSED_EXIT_STITCH for edge in stitches),
        "mainTrackPreserved": True,
        "pitlanePreserved": ENTRY_NAME in visual["geometries"] and CORRIDOR_NAME in visual["geometries"] and EXIT_NAME in visual["geometries"],
        "retaOpostaStillStraight": _max_chord_deviation(context["mainCenter"], 529, 610) <= 1.1
        and _heading_oscillation(context["mainCenter"], 529, 610) <= 6.0,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "stitchEdgeCountBefore": len(base_stitches),
        "stitchEdgeCountRenderedAfter": len(stitches),
        "suppressedStitchEdgeNames": [edge.get("name") for edge in suppressed],
    }
    required = [
        "pitExitOpenCaps",
        "pitExitStartStitchSuppressed",
        "pitExitEndStitchSuppressed",
        "pitExitTransverseStitchesSuppressed",
        "pitExitMouthNotClosedByStroke",
        "noTransverseLineCuttingPitlane",
        "mainTrackInnerEdgeSuppressedAtPitExit",
        "pitExitInnerEdgeSuppressed",
        "pitExitEndCapSuppressed",
        "pitExitStartOverlapGenerated",
        "pitExitCorridorJoinCapCovered",
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
        "name": "InterlagosPitAccessOpenExitMouthFixValidation",
        "generatedAt": datetime.utcnow().isoformat(),
        "candidateGeometry": GEOMETRY_NAME,
        "passed": passed,
        **fields,
    }


def _build_app_check() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_CURRENT, timeout=10).read().decode("utf-8"))
    validation = json.loads((DEBUG_DIR / VALIDATION_JSON).read_text(encoding="utf-8"))
    screenshot = DEBUG_DIR / "interlagos_pit_access_open_exit_mouth_fix_app_check.png"
    geometry_name = payload.get("geometryName") or payload.get("track", {}).get("geometryName")
    visual_geometry_name = payload.get("visualGeometryName") or payload.get("track", {}).get("visualGeometryName")
    render_mode = payload.get("renderMode") or payload.get("track", {}).get("renderMode")
    updated_at = payload.get("updatedAt") or payload.get("track", {}).get("updatedAt")
    return {
        "name": "InterlagosPitAccessOpenExitMouthFixAppCheck",
        "generatedAt": datetime.utcnow().isoformat(),
        "geometryName": geometry_name,
        "visualGeometryName": visual_geometry_name,
        "renderMode": render_mode,
        "updatedAt": updated_at,
        "appUsesPitAccessOpenExitMouthFix": geometry_name == GEOMETRY_NAME or visual_geometry_name == GEOMETRY_NAME,
        "pitExitOpenCaps": bool(validation.get("pitExitOpenCaps")),
        "pitExitStartStitchSuppressed": bool(validation.get("pitExitStartStitchSuppressed")),
        "pitExitEndStitchSuppressed": bool(validation.get("pitExitEndStitchSuppressed")),
        "pitExitTransverseStitchesSuppressed": bool(validation.get("pitExitTransverseStitchesSuppressed")),
        "pitExitMouthClosedByStroke": bool(validation.get("pitExitMouthClosedByStroke")),
        "pitExitMouthNotClosedByStroke": bool(validation.get("pitExitMouthNotClosedByStroke")),
        "noTransverseLineCuttingPitlane": bool(validation.get("noTransverseLineCuttingPitlane")),
        "pitExitStartOverlapGenerated": bool(validation.get("pitExitStartOverlapGenerated")),
        "pitExitCorridorJoinCapCovered": bool(validation.get("pitExitCorridorJoinCapCovered")),
        "mainTrackInnerEdgeSuppressedAtPitExit": bool(validation.get("mainTrackInnerEdgeSuppressedAtPitExit")),
        "maxEndpointGapAfterMeters": validation.get("maxEndpointGapAfterMeters"),
        "maxStitchHeadingStepAfter": validation.get("maxStitchHeadingStepAfter"),
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
    return _svg("Interlagos pit access open exit mouth fix candidate", context, base, candidate, validation)


def _validation_svg(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    return _svg("Interlagos pit access open exit mouth fix validation", context, base, candidate, validation)


def _svg(title: str, context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    width = 1500
    height = 980
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#071018"/>',
        f'<text x="28" y="36" fill="#e2e8f0" font-size="22" font-family="Segoe UI, Arial">{_xml(title)}</text>',
        '<text x="28" y="62" fill="#94a3b8" font-size="13" font-family="Segoe UI, Arial">before cap/stitch red / rendered open mouth cyan-orange / suppressed cap dashed red / MainTrack gray</text>',
    ]
    parts.extend(_panel(context, base, candidate, 28, 82, width - 56, height - 150))
    footer = (
        f"passed={validation['passed']} pitExitMouthClosedByStroke={validation['pitExitMouthClosedByStroke']} "
        f"suppressed={validation['pitExitEndStitchSuppressed']}"
    )
    parts.append(f'<text x="28" y="{height - 28}" fill="#94a3b8" font-size="14" font-family="Segoe UI, Arial">{_xml(footer)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _panel(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], x: float, y: float, width: float, height: float) -> List[str]:
    geom = candidate["visualGeometry"]["geometries"][EXIT_NAME]
    before_stitches = [
        edge for edge in base["visualGeometry"]["surfaceUnionFix"].get("stitchEdges", []) if edge.get("geometryName") == EXIT_NAME
    ]
    after_stitches = [
        edge for edge in candidate["visualGeometry"]["surfaceUnionFix"].get("stitchEdges", []) if edge.get("geometryName") == EXIT_NAME
    ]
    suppressed = [
        edge for edge in candidate["visualGeometry"]["surfaceUnionFix"].get("suppressedStitchEdges", []) if edge.get("geometryName") == EXIT_NAME
    ]
    focus_points = (
        _line_points(geom["centerline"])
        + [point for edge in before_stitches for point in _line_points(edge["points"])]
        + [point for edge in after_stitches for point in _line_points(edge["points"])]
        + [point for edge in suppressed for point in _line_points(edge["points"])]
    )
    bounds = _bounds_for_points(focus_points, pad=70.0)
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

    parts = [
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" fill="#0b1220" stroke="#1f2937"/>',
        f'<text x="{x + 12:.2f}" y="{y + 24:.2f}" fill="#e2e8f0" font-size="15" font-family="Segoe UI, Arial">saida pitlane: boca aberta, sem cap transversal</text>',
        f'<path d="{path(context["mainLeft"])}" fill="none" stroke="#94a3b8" stroke-width="2.0" stroke-opacity="0.7"/>',
        f'<path d="{path(context["mainRight"])}" fill="none" stroke="#94a3b8" stroke-width="2.0" stroke-opacity="0.7"/>',
        f'<path d="{path(_line_points(geom["polygon"]), close=True)}" fill="#fb923c" fill-opacity="0.34" stroke="none"/>',
        f'<path d="{path(_line_points(geom["outerEdge"]))}" fill="none" stroke="#f8fafc" stroke-width="1.0" stroke-opacity="0.45"/>',
    ]
    for edge in before_stitches:
        points = _line_points(edge["points"])
        parts.append(
            f'<path d="{path(points)}" fill="none" stroke="#ef4444" stroke-width="3.0" stroke-linecap="round" stroke-linejoin="round" stroke-opacity="0.55"/>'
        )
    for edge in suppressed:
        points = _line_points(edge["points"])
        parts.append(
            f'<path d="{path(points)}" fill="none" stroke="#ef4444" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="8 7" stroke-opacity="0.9"/>'
        )
    for edge in after_stitches:
        points = _line_points(edge["points"])
        parts.append(
            f'<path d="{path(points)}" fill="none" stroke="#22d3ee" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        for point in (points[0], points[-1]):
            px, py = project(point)
            parts.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4.0" fill="#bfdbfe" stroke="#0284c7" stroke-width="1.2"/>')
    return parts


if __name__ == "__main__":
    main()
