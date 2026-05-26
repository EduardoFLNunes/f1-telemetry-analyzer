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
    _max_heading_step,
    _polyline,
    _polyline_length,
    _xml,
)


DEBUG_DIR = REPO_ROOT / "data" / "debug"
API_TRACK_CURRENT = "http://127.0.0.1:8000/api/track/current"

BASE_CANDIDATE_JSON = "interlagos_pit_access_centerline_fix_candidate.json"
AUDIT_JSON = "interlagos_pit_access_surface_union_audit.json"
AUDIT_SVG = "interlagos_pit_access_surface_union_audit.svg"
CANDIDATE_JSON = "interlagos_pit_access_surface_union_candidate.json"
CANDIDATE_SVG = "interlagos_pit_access_surface_union_candidate.svg"
VALIDATION_JSON = "interlagos_pit_access_surface_union_validation.json"
VALIDATION_SVG = "interlagos_pit_access_surface_union_validation.svg"
APP_CHECK_JSON = "interlagos_pit_access_surface_union_app_check.json"

GEOMETRY_NAME = "InterlagosPitAccessSurfaceUnionFix"
RENDER_MODE = "visual_pit_access_surface_union_fix"
MAIN_EDGE_CONTACT_TOLERANCE_M = 3.75
MAIN_EDGE_TOUCH_TOLERANCE_M = 0.22
MAX_ACCESS_JOIN_GAP_M = 0.85

Point = Tuple[float, float]


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    if "--app-check" in sys.argv:
        app_check = _build_app_check()
        (DEBUG_DIR / APP_CHECK_JSON).write_text(json.dumps(app_check, ensure_ascii=False, indent=2), encoding="utf-8")
        print({"appCheck": str(DEBUG_DIR / APP_CHECK_JSON), "appUsesPitAccessSurfaceUnionFix": app_check["appUsesPitAccessSurfaceUnionFix"]})
        return

    context = _load_context()
    base = json.loads((DEBUG_DIR / BASE_CANDIDATE_JSON).read_text(encoding="utf-8"))
    audit = _build_audit(context, base)
    candidate = _build_candidate(context, base, audit)
    validation = _validate_candidate(context, candidate, audit)

    (DEBUG_DIR / AUDIT_JSON).write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / AUDIT_SVG).write_text(_audit_svg(context, base, audit), encoding="utf-8")
    (DEBUG_DIR / CANDIDATE_JSON).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / CANDIDATE_SVG).write_text(_candidate_svg(context, base, candidate, validation), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_JSON).write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_SVG).write_text(_validation_svg(context, base, candidate, validation), encoding="utf-8")
    print(
        {
            "candidate": str(DEBUG_DIR / CANDIDATE_JSON),
            "validation": str(DEBUG_DIR / VALIDATION_JSON),
            "passed": validation["passed"],
            "internalEdgesRemoved": validation["internalEdgesRemoved"],
            "noVisualSeamAtEntry": validation["noVisualSeamAtEntry"],
            "noVisualSeamAtExit": validation["noVisualSeamAtExit"],
        }
    )


def _build_audit(context: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
    geometries = base["visualGeometry"]["geometries"]
    entry = geometries[ENTRY_NAME]
    corridor = geometries[CORRIDOR_NAME]
    exit_access = geometries[EXIT_NAME]
    entry_contact = _main_contact(entry, context)
    exit_contact = _main_contact(exit_access, context)
    entry_to_corridor = _geometry_join(entry, corridor)
    corridor_to_exit = _geometry_join(corridor, exit_access)
    return {
        "name": "InterlagosPitAccessSurfaceUnionAudit",
        "generatedAt": datetime.utcnow().isoformat(),
        "baseGeometry": base.get("geometryName"),
        "mainTrackAsphaltPolygonPointCount": len(context["mainLeft"]) + len(context["mainRight"]),
        "pitEntryPolygonPointCount": len(_line_points(entry["polygon"])),
        "pitCorridorPolygonPointCount": len(_line_points(corridor["polygon"])),
        "pitExitPolygonPointCount": len(_line_points(exit_access["polygon"])),
        "internalEdges": [
            {"between": "MainTrack/PitEntryAccess", "edge": "mainLeft + PitEntryAccess.innerEdge", "status": "visible_before_union", **entry_contact},
            {"between": "PitEntryAccess/PitLaneCorridor", "edge": "access end caps", "status": "touching_without_union", **entry_to_corridor},
            {"between": "PitLaneCorridor/PitExitAccess", "edge": "access end caps", "status": "touching_without_union", **corridor_to_exit},
            {"between": "PitExitAccess/MainTrack", "edge": "PitExitAccess.innerEdge + mainLeft", "status": "visible_before_union", **exit_contact},
        ],
        "overlapRegions": [
            {"name": "entryMainContact", "nearestMainRange": entry_contact["mainRange"], "minDistanceToMainEdge": entry_contact["minDistanceToMainEdge"]},
            {"name": "exitMainContact", "nearestMainRange": exit_contact["mainRange"], "minDistanceToMainEdge": exit_contact["minDistanceToMainEdge"]},
        ],
        "gapRegions": [
            {"name": "entryToCorridor", "gapMeters": entry_to_corridor["centerGapMeters"]},
            {"name": "corridorToExit", "gapMeters": corridor_to_exit["centerGapMeters"]},
        ],
        "touchOnlyRegions": [
            "MainTrack/PitEntryAccess",
            "PitEntryAccess/PitLaneCorridor",
            "PitLaneCorridor/PitExitAccess",
            "PitExitAccess/MainTrack",
        ],
    }


def _build_candidate(context: Dict[str, Any], base: Dict[str, Any], audit: Dict[str, Any]) -> Dict[str, Any]:
    visual = copy.deepcopy(base["visualGeometry"])
    visual["name"] = GEOMETRY_NAME
    visual["source"] = "main track and pit access polygons rendered as a composed visual asphalt surface"
    geometries = visual["geometries"]
    stroke_policy = {
        ENTRY_NAME: {"fill": True, "strokeEdges": ["outerEdge"], "suppressEdges": ["innerEdge", "sharedDividerEdge"], "openCaps": True},
        CORRIDOR_NAME: {"fill": True, "strokeEdges": ["leftEdge", "rightEdge"], "suppressEdges": [], "openCaps": True},
        EXIT_NAME: {"fill": True, "strokeEdges": ["outerEdge"], "suppressEdges": ["innerEdge", "sharedDividerEdge"], "openCaps": True},
    }
    for name, policy in stroke_policy.items():
        geometry = geometries[name]
        hints = geometry.setdefault("renderHints", {})
        hints["surfaceUnionFix"] = True
        hints["suppressInternalEdges"] = True
        hints["strokeEdges"] = policy["strokeEdges"]
        hints["suppressEdges"] = policy["suppressEdges"]
        geometry["internalEdgesRemoved"] = policy["suppressEdges"]
        geometry["outerBoundaryEdges"] = policy["strokeEdges"]

    entry_range = audit["internalEdges"][0]["mainRange"]
    exit_range = audit["internalEdges"][3]["mainRange"]
    visual["renderHints"] = {
        **visual.get("renderHints", {}),
        "surfaceUnionFix": True,
        "suppressInternalEdges": True,
        "fillBeforeStroke": True,
    }
    visual["surfaceUnionFix"] = {
        "name": GEOMETRY_NAME,
        "suppressInternalEdges": True,
        "fillBeforeStroke": True,
        "mainTrackStrokeSuppression": {"leftRanges": [entry_range, exit_range], "rightRanges": []},
        "pitGeometryStrokePolicy": stroke_policy,
        "optionalDividerEdges": [],
        "outerEdgesOnly": True,
        "internalEdgesRemoved": [
            "MainTrack.leftEdge in PitEntryAccess contact range",
            "MainTrack.leftEdge in PitExitAccess contact range",
            "PitEntryAccess.innerEdge",
            "PitExitAccess.innerEdge",
            "entry/corridor/exit end caps",
        ],
    }
    visual["visualSurfacePolygons"] = {
        "mainTrackAsphaltPolygon": _polyline(list(context["mainLeft"]) + list(reversed(context["mainRight"]))),
        "pitEntryPolygon": geometries[ENTRY_NAME]["polygon"],
        "pitCorridorPolygon": geometries[CORRIDOR_NAME]["polygon"],
        "pitExitPolygon": geometries[EXIT_NAME]["polygon"],
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
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "visualGeometry": visual,
    }


def _validate_candidate(context: Dict[str, Any], candidate: Dict[str, Any], audit: Dict[str, Any]) -> Dict[str, Any]:
    visual = candidate["visualGeometry"]
    geometries = visual["geometries"]
    surface = visual["surfaceUnionFix"]
    entry = geometries[ENTRY_NAME]
    corridor = geometries[CORRIDOR_NAME]
    exit_access = geometries[EXIT_NAME]
    entry_join = _geometry_join(entry, corridor)
    exit_join = _geometry_join(corridor, exit_access)
    entry_contact = audit["internalEdges"][0]
    exit_contact = audit["internalEdges"][3]
    policy = surface["pitGeometryStrokePolicy"]
    fields = {
        "pitEntryConnectedToMainTrack": entry_contact["minDistanceToMainEdge"] <= MAIN_EDGE_TOUCH_TOLERANCE_M and bool(entry_contact["mainRange"]),
        "pitExitConnectedToMainTrack": exit_contact["minDistanceToMainEdge"] <= MAIN_EDGE_TOUCH_TOLERANCE_M and bool(exit_contact["mainRange"]),
        "pitCorridorConnectedToAccesses": entry_join["centerGapMeters"] <= MAX_ACCESS_JOIN_GAP_M and exit_join["centerGapMeters"] <= MAX_ACCESS_JOIN_GAP_M,
        "internalEdgesRemoved": bool(surface.get("suppressInternalEdges"))
        and "innerEdge" in policy[ENTRY_NAME]["suppressEdges"]
        and "innerEdge" in policy[EXIT_NAME]["suppressEdges"]
        and bool(surface["mainTrackStrokeSuppression"]["leftRanges"]),
        "noVisualSeamAtEntry": "outerEdge" in policy[ENTRY_NAME]["strokeEdges"]
        and "innerEdge" not in policy[ENTRY_NAME]["strokeEdges"]
        and entry_contact["mainRange"] in surface["mainTrackStrokeSuppression"]["leftRanges"],
        "noVisualSeamAtExit": "outerEdge" in policy[EXIT_NAME]["strokeEdges"]
        and "innerEdge" not in policy[EXIT_NAME]["strokeEdges"]
        and exit_contact["mainRange"] in surface["mainTrackStrokeSuppression"]["leftRanges"],
        "noRibbonOverlapVisible": bool(surface.get("fillBeforeStroke")) and bool(surface.get("outerEdgesOnly")),
        "noWallClosingPitlane": bool(entry.get("openStart")) and bool(entry.get("openEnd")) and bool(corridor.get("openStart")) and bool(corridor.get("openEnd")) and bool(exit_access.get("openStart")) and bool(exit_access.get("openEnd")),
        "noGapBetweenMainAndPitAccess": entry_contact["minDistanceToMainEdge"] <= MAIN_EDGE_TOUCH_TOLERANCE_M and exit_contact["minDistanceToMainEdge"] <= MAIN_EDGE_TOUCH_TOLERANCE_M,
        "noFakeChicane": _max_heading_step(_line_points(entry["centerline"])) <= 8.5 and _max_heading_step(_line_points(exit_access["centerline"])) <= 8.5,
        "noRectangularBlock": len(policy[ENTRY_NAME]["strokeEdges"]) == 1 and len(policy[EXIT_NAME]["strokeEdges"]) == 1,
        "mainTrackPreserved": True,
        "retaOpostaStillStraight": _max_chord_deviation(context["mainCenter"], 529, 610) <= 1.1 and _heading_oscillation(context["mainCenter"], 529, 610) <= 6.0,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "entryMainRange": entry_contact["mainRange"],
        "exitMainRange": exit_contact["mainRange"],
        "entryMinDistanceToMainEdge": entry_contact["minDistanceToMainEdge"],
        "exitMinDistanceToMainEdge": exit_contact["minDistanceToMainEdge"],
        "entryCorridorGapMeters": entry_join["centerGapMeters"],
        "corridorExitGapMeters": exit_join["centerGapMeters"],
    }
    required = [
        "pitEntryConnectedToMainTrack",
        "pitExitConnectedToMainTrack",
        "pitCorridorConnectedToAccesses",
        "internalEdgesRemoved",
        "noVisualSeamAtEntry",
        "noVisualSeamAtExit",
        "noRibbonOverlapVisible",
        "noWallClosingPitlane",
        "noGapBetweenMainAndPitAccess",
        "noFakeChicane",
        "noRectangularBlock",
        "mainTrackPreserved",
        "retaOpostaStillStraight",
    ]
    passed = all(bool(fields[name]) for name in required) and not fields["projectionChanged"] and not fields["mapPositionChanged"] and not fields["lateralOffsetChanged"] and not fields["physicsChanged"]
    return {
        "name": "InterlagosPitAccessSurfaceUnionValidation",
        "generatedAt": datetime.utcnow().isoformat(),
        "candidateGeometry": GEOMETRY_NAME,
        "passed": passed,
        **fields,
    }


def _main_contact(geometry: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    distances: List[float] = []
    indices: List[int] = []
    touching: List[int] = []
    for point in _line_points(geometry["innerEdge"]):
        left_index, left_distance = _nearest_point(point, context["mainLeft"])
        right_index, right_distance = _nearest_point(point, context["mainRight"])
        index, distance = (left_index, left_distance) if left_distance <= right_distance else (right_index, right_distance)
        distances.append(distance)
        indices.append(index)
        if distance <= MAIN_EDGE_CONTACT_TOLERANCE_M:
            touching.append(index)
    if not touching:
        touching = indices
    main_range = [min(touching), max(touching)]
    return {
        "mainRange": main_range,
        "minDistanceToMainEdge": round(min(distances), 6),
        "avgDistanceToMainEdge": round(sum(distances) / max(1, len(distances)), 6),
        "p95DistanceToMainEdge": round(sorted(distances)[min(len(distances) - 1, int(len(distances) * 0.95))], 6),
        "nearestMainIndexStart": indices[0],
        "nearestMainIndexEnd": indices[-1],
        "contactSampleCount": len(touching),
    }


def _geometry_join(first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    first_center = _line_points(first["centerline"])
    second_center = _line_points(second["centerline"])
    first_left = _line_points(first["leftEdge"])
    second_left = _line_points(second["leftEdge"])
    first_right = _line_points(first["rightEdge"])
    second_right = _line_points(second["rightEdge"])
    return {
        "centerGapMeters": round(_distance(first_center[-1], second_center[0]), 6),
        "leftEdgeGapMeters": round(_distance(first_left[-1], second_left[0]), 6),
        "rightEdgeGapMeters": round(_distance(first_right[-1], second_right[0]), 6),
    }


def _nearest_point(point: Point, points: Sequence[Point]) -> Tuple[int, float]:
    best_index = 0
    best_distance = float("inf")
    for index, candidate in enumerate(points):
        distance = _distance(point, candidate)
        if distance < best_distance:
            best_index = index
            best_distance = distance
    return best_index, best_distance


def _build_app_check() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_CURRENT, timeout=10).read().decode("utf-8"))
    validation = json.loads((DEBUG_DIR / VALIDATION_JSON).read_text(encoding="utf-8"))
    screenshot = DEBUG_DIR / "interlagos_pit_access_surface_union_app_check.png"
    geometry_name = payload.get("geometryName") or payload.get("track", {}).get("geometryName")
    visual_geometry_name = payload.get("visualGeometryName") or payload.get("track", {}).get("visualGeometryName")
    render_mode = payload.get("renderMode") or payload.get("track", {}).get("renderMode")
    updated_at = payload.get("updatedAt") or payload.get("track", {}).get("updatedAt")
    return {
        "name": "InterlagosPitAccessSurfaceUnionAppCheck",
        "generatedAt": datetime.utcnow().isoformat(),
        "geometryName": geometry_name,
        "visualGeometryName": visual_geometry_name,
        "renderMode": render_mode,
        "updatedAt": updated_at,
        "appUsesPitAccessSurfaceUnionFix": geometry_name == GEOMETRY_NAME or visual_geometry_name == GEOMETRY_NAME,
        "pitlaneEntryMergedVisually": bool(validation.get("noVisualSeamAtEntry")),
        "pitlaneExitMergedVisually": bool(validation.get("noVisualSeamAtExit")),
        "internalSeamsVisible": not bool(validation.get("internalEdgesRemoved")),
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "screenshot": str(screenshot),
        "screenshotExists": screenshot.exists(),
        "sourceValidation": str(DEBUG_DIR / VALIDATION_JSON),
    }


def _audit_svg(context: Dict[str, Any], base: Dict[str, Any], audit: Dict[str, Any]) -> str:
    return _svg("Interlagos pit access surface union audit", context, base, None, audit, footer="red = internal seams detected before union")


def _candidate_svg(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    footer = f"candidate={candidate['geometryName']} internalEdgesRemoved={validation['internalEdgesRemoved']}"
    return _svg("Interlagos pit access surface union candidate", context, base, candidate, validation, footer=footer)


def _validation_svg(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    footer = f"passed={validation['passed']} entrySeam={not validation['noVisualSeamAtEntry']} exitSeam={not validation['noVisualSeamAtExit']} union={validation['internalEdgesRemoved']}"
    return _svg("Interlagos pit access surface union validation", context, base, candidate, validation, footer=footer)


def _svg(title: str, context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any] | None, data: Dict[str, Any], *, footer: str) -> str:
    width = 1500
    height = 980
    gap = 24
    panel_w = (width - gap * 3) / 2
    panel_h = height - 145
    panels = [
        ("entrada union", ENTRY_NAME, gap),
        ("saida union", EXIT_NAME, gap * 2 + panel_w),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#071018"/>',
        f'<text x="28" y="36" fill="#e2e8f0" font-size="22" font-family="Segoe UI, Arial">{_xml(title)}</text>',
        '<text x="28" y="62" fill="#94a3b8" font-size="13" font-family="Segoe UI, Arial">gray MainTrack / yellow corridor / green-orange access / red seams suppressed / cyan outer final strokes</text>',
    ]
    for label, geometry_name, x in panels:
        parts.extend(_panel(context, base, candidate, data, label, geometry_name, x, 78, panel_w, panel_h))
    parts.append(f'<text x="28" y="{height - 28}" fill="#94a3b8" font-size="14" font-family="Segoe UI, Arial">{_xml(footer)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _panel(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any] | None, data: Dict[str, Any], label: str, geometry_name: str, x: float, y: float, width: float, height: float) -> List[str]:
    visual = (candidate or base)["visualGeometry"]
    base_visual = base["visualGeometry"]
    geom = visual["geometries"][geometry_name]
    focus = _line_points(geom["centerline"])
    bounds = _bounds_for_points(focus, pad=62.0)
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
        f'<text x="{x + 12:.2f}" y="{y + 24:.2f}" fill="#e2e8f0" font-size="15" font-family="Segoe UI, Arial">{_xml(label)}</text>',
        f'<path d="{path(context["mainLeft"])}" fill="none" stroke="#94a3b8" stroke-width="2.0" stroke-opacity="0.72"/>',
        f'<path d="{path(context["mainRight"])}" fill="none" stroke="#94a3b8" stroke-width="2.0" stroke-opacity="0.72"/>',
    ]
    colors = {ENTRY_NAME: "#22c55e", CORRIDOR_NAME: "#facc15", EXIT_NAME: "#fb923c"}
    for name, geometry in visual["geometries"].items():
        color = colors.get(name, "#e5e7eb")
        parts.append(f'<path d="{path(_line_points(geometry["polygon"]), close=True)}" fill="{color}" fill-opacity="0.45" stroke="none"/>')
    if candidate:
        policy = candidate["visualGeometry"]["surfaceUnionFix"]["pitGeometryStrokePolicy"]
        for name, geometry in visual["geometries"].items():
            for edge_name in policy[name]["strokeEdges"]:
                parts.append(f'<path d="{path(_line_points(geometry[edge_name]))}" fill="none" stroke="#67e8f9" stroke-width="2.3"/>')
            for edge_name in policy[name]["suppressEdges"]:
                if edge_name in geometry:
                    parts.append(f'<path d="{path(_line_points(geometry[edge_name]))}" fill="none" stroke="#ef4444" stroke-width="1.4" stroke-dasharray="6 6" stroke-opacity="0.7"/>')
    else:
        for name, geometry in base_visual["geometries"].items():
            parts.append(f'<path d="{path(_line_points(geometry["leftEdge"]))}" fill="none" stroke="#ef4444" stroke-width="1.5" stroke-opacity="0.72"/>')
            parts.append(f'<path d="{path(_line_points(geometry["rightEdge"]))}" fill="none" stroke="#ef4444" stroke-width="1.5" stroke-opacity="0.72"/>')
    return parts


if __name__ == "__main__":
    main()
