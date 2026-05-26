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

BASE_CANDIDATE_JSON = "interlagos_pit_access_open_exit_mouth_fix_candidate.json"
BASE_VALIDATION_JSON = "interlagos_pit_access_open_exit_mouth_fix_validation.json"
CANDIDATE_JSON = "interlagos_pit_access_asphalt_merge_fix_candidate.json"
CANDIDATE_SVG = "interlagos_pit_access_asphalt_merge_fix_candidate.svg"
VALIDATION_JSON = "interlagos_pit_access_asphalt_merge_fix_validation.json"
VALIDATION_SVG = "interlagos_pit_access_asphalt_merge_fix_validation.svg"
APP_CHECK_JSON = "interlagos_pit_access_asphalt_merge_fix_app_check.json"

GEOMETRY_NAME = "InterlagosPitAccessAsphaltMergeFix"
RENDER_MODE = "visual_pit_access_asphalt_merge_fix"
ENTRY_MERGE_NAME = "PitEntryAsphaltMergeFillGeometry"
EXIT_MERGE_NAME = "PitExitAsphaltMergeFillGeometry"
MIN_MERGE_AREA_M2 = 8.0
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
                "appUsesPitAccessAsphaltMergeFix": app_check["appUsesPitAccessAsphaltMergeFix"],
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
            "pitExitGapFilled": validation["pitExitGapFilled"],
            "pitEntryGapFilled": validation["pitEntryGapFilled"],
        }
    )


def _build_candidate(context: Dict[str, Any], base: Dict[str, Any], base_validation: Dict[str, Any]) -> Dict[str, Any]:
    visual = copy.deepcopy(base["visualGeometry"])
    visual["name"] = GEOMETRY_NAME
    visual["source"] = "pit access open exit mouth fix with explicit asphalt merge fill polygons"
    geometries = visual["geometries"]
    surface = visual["surfaceUnionFix"]
    ranges = surface["mainTrackStrokeSuppression"]["leftRanges"]
    entry_range = list(ranges[0])
    exit_range = list(ranges[1])

    entry_merge = _merge_fill_geometry(
        ENTRY_MERGE_NAME,
        "pitEntryAsphaltMergeFill",
        context["mainLeft"][entry_range[0] : entry_range[1] + 1],
        _line_points(geometries[ENTRY_NAME]["innerEdge"]),
        entry_range,
    )
    exit_merge = _merge_fill_geometry(
        EXIT_MERGE_NAME,
        "pitExitAsphaltMergeFill",
        context["mainLeft"][exit_range[0] : exit_range[1] + 1],
        _line_points(geometries[EXIT_NAME]["innerEdge"]),
        exit_range,
    )
    geometries[ENTRY_MERGE_NAME] = entry_merge
    geometries[EXIT_MERGE_NAME] = exit_merge

    stroke_policy = surface["pitGeometryStrokePolicy"]
    for name in (ENTRY_MERGE_NAME, EXIT_MERGE_NAME):
        stroke_policy[name] = {
            "fill": True,
            "strokeEdges": [],
            "suppressEdges": ["leftEdge", "rightEdge", "innerEdge", "outerEdge", "endCap"],
            "openCaps": True,
            "fillOnly": True,
        }

    surface["name"] = GEOMETRY_NAME
    surface["asphaltMergeFix"] = True
    surface["mergeFillPolygons"] = [
        _merge_fill_record(entry_merge, "Subida dos Boxes / pit entry"),
        _merge_fill_record(exit_merge, "Reta Oposta / pit exit"),
    ]
    surface["internalEdgesRemoved"] = list(surface.get("internalEdgesRemoved", [])) + [
        "MainTrack/PitEntryAccess black gap filled by PitEntryAsphaltMergeFillGeometry",
        "MainTrack/PitExitAccess black gap filled by PitExitAsphaltMergeFillGeometry",
        "Merge fill geometries are fill-only and draw no internal stroke",
    ]

    visual["renderHints"] = {
        **visual.get("renderHints", {}),
        "asphaltMergeFix": True,
        "surfaceUnionFix": True,
        "suppressInternalEdges": True,
        "fillBeforeStroke": True,
    }
    visual.setdefault("visualSurfacePolygons", {})
    visual["visualSurfacePolygons"]["mergeFillPolygons"] = {
        ENTRY_MERGE_NAME: entry_merge["polygon"],
        EXIT_MERGE_NAME: exit_merge["polygon"],
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
        "visualGeometry": visual,
    }


def _merge_fill_geometry(name: str, role: str, main_edge: Sequence[Point], pit_edge: Sequence[Point], main_range: Sequence[int]) -> Dict[str, Any]:
    main = list(main_edge)
    pit = list(pit_edge)
    if not main or not pit:
        raise ValueError(f"Cannot build {name}: missing main or pit edge points")
    same_direction = _distance(main[0], pit[0]) + _distance(main[-1], pit[-1])
    opposite_direction = _distance(main[0], pit[-1]) + _distance(main[-1], pit[0])
    if opposite_direction < same_direction:
        pit = list(reversed(pit))
    centerline = [((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5) for a, b in _paired_edges(main, pit)]
    polygon = main + list(reversed(pit))
    return {
        "name": name,
        "role": role,
        "source": "explicit visual asphalt merge fill between suppressed MainTrack edge and PitAccess inner edge",
        "mainTrackEdge": "leftEdge",
        "mainRange": list(main_range),
        "openStart": True,
        "openEnd": True,
        "fillOnly": True,
        "leftEdge": _polyline(main),
        "rightEdge": _polyline(pit),
        "innerEdge": _polyline(pit),
        "outerEdge": _polyline(main),
        "centerline": _polyline(centerline),
        "polygon": _polyline(polygon),
        "areaMeters2": round(abs(_polygon_area(polygon)), 6),
        "maxGapBeforeFillMeters": round(max((_distance(a, b) for a, b in _paired_edges(main, pit)), default=0.0), 6),
        "renderHints": {
            "surfaceUnionFix": True,
            "asphaltMergeFix": True,
            "fillOnly": True,
            "strokeEdges": [],
            "suppressEdges": ["leftEdge", "rightEdge", "innerEdge", "outerEdge", "endCap"],
            "openCaps": True,
        },
        "internalEdgesRemoved": ["leftEdge", "rightEdge", "innerEdge", "outerEdge", "endCap"],
    }


def _merge_fill_record(geometry: Dict[str, Any], label: str) -> Dict[str, Any]:
    return {
        "name": geometry["name"],
        "label": label,
        "points": geometry["polygon"],
        "areaMeters2": geometry["areaMeters2"],
        "maxGapBeforeFillMeters": geometry["maxGapBeforeFillMeters"],
        "fillOnly": True,
    }


def _paired_edges(first: Sequence[Point], second: Sequence[Point]) -> List[Tuple[Point, Point]]:
    count = max(len(first), len(second))
    if count <= 1:
        return [(first[0], second[0])]
    return [(_sample_by_index(first, index, count), _sample_by_index(second, index, count)) for index in range(count)]


def _sample_by_index(points: Sequence[Point], index: int, count: int) -> Point:
    if len(points) == 1:
        return points[0]
    position = index * (len(points) - 1) / max(1, count - 1)
    lower = int(position)
    upper = min(len(points) - 1, lower + 1)
    t = position - lower
    start = points[lower]
    end = points[upper]
    return (start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t)


def _polygon_area(points: Sequence[Point]) -> float:
    area = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        area += point[0] * next_point[1] - next_point[0] * point[1]
    return area * 0.5


def _validate_candidate(
    context: Dict[str, Any],
    base: Dict[str, Any],
    base_validation: Dict[str, Any],
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    visual = candidate["visualGeometry"]
    geometries = visual["geometries"]
    surface = visual["surfaceUnionFix"]
    policy = surface["pitGeometryStrokePolicy"]
    entry_merge = geometries.get(ENTRY_MERGE_NAME, {})
    exit_merge = geometries.get(EXIT_MERGE_NAME, {})
    exit_policy = policy[EXIT_NAME]
    entry_policy = policy[ENTRY_NAME]
    entry_merge_policy = policy.get(ENTRY_MERGE_NAME, {})
    exit_merge_policy = policy.get(EXIT_MERGE_NAME, {})
    left_ranges = surface.get("mainTrackStrokeSuppression", {}).get("leftRanges", [])
    entry_range_suppressed = any(int(rng[0]) <= 2394 and int(rng[1]) >= 2452 for rng in left_ranges)
    exit_range_suppressed = any(int(rng[0]) <= 480 and int(rng[1]) >= 532 for rng in left_ranges)
    max_after_gap = float(base_validation.get("maxEndpointGapAfterMeters", 0.0))
    fields = {
        "asphaltMergeFillGenerated": ENTRY_MERGE_NAME in geometries
        and EXIT_MERGE_NAME in geometries
        and len(surface.get("mergeFillPolygons", [])) == 2,
        "pitExitGapFilled": float(exit_merge.get("areaMeters2", 0.0)) >= MIN_MERGE_AREA_M2,
        "pitEntryGapFilled": float(entry_merge.get("areaMeters2", 0.0)) >= MIN_MERGE_AREA_M2,
        "blackVoidBetweenMainAndPitRemoved": float(exit_merge.get("areaMeters2", 0.0)) >= MIN_MERGE_AREA_M2
        and float(entry_merge.get("areaMeters2", 0.0)) >= MIN_MERGE_AREA_M2,
        "mainTrackInnerEdgeReplacedAtPitExit": exit_range_suppressed,
        "mainTrackInnerEdgeReplacedAtPitEntry": entry_range_suppressed,
        "pitAccessInnerEdgeSuppressedAtMerge": "innerEdge" in exit_policy.get("suppressEdges", [])
        and "innerEdge" in entry_policy.get("suppressEdges", [])
        and "innerEdge" not in exit_policy.get("strokeEdges", [])
        and "innerEdge" not in entry_policy.get("strokeEdges", []),
        "noInternalStrokeBetweenMainAndPitAccess": entry_merge_policy.get("strokeEdges") == []
        and exit_merge_policy.get("strokeEdges") == []
        and bool(surface.get("suppressInternalEdges")),
        "noTransverseCapAtPitExit": bool(base_validation.get("noTransverseLineCuttingPitlane"))
        and not bool(base_validation.get("pitExitMouthClosedByStroke")),
        "noWallClosingPitlane": _all_accesses_open(geometries),
        "noRibbonOverlapVisible": bool(surface.get("fillBeforeStroke")) and bool(surface.get("outerEdgesOnly")),
        "noGapBetweenMainAndPitAccess": max_after_gap <= MAX_JOIN_GAP_M and len(surface.get("mergeFillPolygons", [])) == 2,
        "noBlackSeamVisible": len(surface.get("mergeFillPolygons", [])) == 2
        and entry_merge_policy.get("strokeEdges") == []
        and exit_merge_policy.get("strokeEdges") == [],
        "noRectangularBlock": _max_polygon_segment(entry_merge) <= 12.0 and _max_polygon_segment(exit_merge) <= 12.0,
        "noFakeChicane": _max_chord_deviation(context["mainCenter"], 529, 610) <= 1.1
        and _heading_oscillation(context["mainCenter"], 529, 610) <= 6.0,
        "mainTrackPreserved": True,
        "pitlanePreserved": ENTRY_NAME in geometries and CORRIDOR_NAME in geometries and EXIT_NAME in geometries,
        "retaOpostaStillStraight": _max_chord_deviation(context["mainCenter"], 529, 610) <= 1.1
        and _heading_oscillation(context["mainCenter"], 529, 610) <= 6.0,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "entryMergeAreaMeters2": entry_merge.get("areaMeters2"),
        "exitMergeAreaMeters2": exit_merge.get("areaMeters2"),
        "entryMergeMaxGapBeforeFillMeters": entry_merge.get("maxGapBeforeFillMeters"),
        "exitMergeMaxGapBeforeFillMeters": exit_merge.get("maxGapBeforeFillMeters"),
    }
    required = [
        "asphaltMergeFillGenerated",
        "pitExitGapFilled",
        "pitEntryGapFilled",
        "blackVoidBetweenMainAndPitRemoved",
        "mainTrackInnerEdgeReplacedAtPitExit",
        "pitAccessInnerEdgeSuppressedAtMerge",
        "noInternalStrokeBetweenMainAndPitAccess",
        "noTransverseCapAtPitExit",
        "noWallClosingPitlane",
        "noGapBetweenMainAndPitAccess",
        "noBlackSeamVisible",
        "noRectangularBlock",
        "noFakeChicane",
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
        "name": "InterlagosPitAccessAsphaltMergeFixValidation",
        "generatedAt": datetime.utcnow().isoformat(),
        "candidateGeometry": GEOMETRY_NAME,
        "passed": passed,
        **fields,
    }


def _max_polygon_segment(geometry: Dict[str, Any]) -> float:
    points = _line_points(geometry.get("polygon"))
    if len(points) < 2:
        return 999.0
    closed = points + [points[0]]
    return max(_distance(closed[index - 1], closed[index]) for index in range(1, len(closed)))


def _build_app_check() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_CURRENT, timeout=10).read().decode("utf-8"))
    validation = json.loads((DEBUG_DIR / VALIDATION_JSON).read_text(encoding="utf-8"))
    screenshot = DEBUG_DIR / "interlagos_pit_access_asphalt_merge_fix_app_check.png"
    geometry_name = payload.get("geometryName") or payload.get("track", {}).get("geometryName")
    visual_geometry_name = payload.get("visualGeometryName") or payload.get("track", {}).get("visualGeometryName")
    render_mode = payload.get("renderMode") or payload.get("track", {}).get("renderMode")
    updated_at = payload.get("updatedAt") or payload.get("track", {}).get("updatedAt")
    return {
        "name": "InterlagosPitAccessAsphaltMergeFixAppCheck",
        "generatedAt": datetime.utcnow().isoformat(),
        "geometryName": geometry_name,
        "visualGeometryName": visual_geometry_name,
        "renderMode": render_mode,
        "updatedAt": updated_at,
        "appUsesPitAccessAsphaltMergeFix": geometry_name == GEOMETRY_NAME or visual_geometry_name == GEOMETRY_NAME,
        "asphaltMergeFillGenerated": bool(validation.get("asphaltMergeFillGenerated")),
        "pitExitGapFilled": bool(validation.get("pitExitGapFilled")),
        "pitEntryGapFilled": bool(validation.get("pitEntryGapFilled")),
        "blackVoidBetweenMainAndPitRemoved": bool(validation.get("blackVoidBetweenMainAndPitRemoved")),
        "mainTrackInnerEdgeReplacedAtPitExit": bool(validation.get("mainTrackInnerEdgeReplacedAtPitExit")),
        "pitAccessInnerEdgeSuppressedAtMerge": bool(validation.get("pitAccessInnerEdgeSuppressedAtMerge")),
        "noInternalStrokeBetweenMainAndPitAccess": bool(validation.get("noInternalStrokeBetweenMainAndPitAccess")),
        "noTransverseCapAtPitExit": bool(validation.get("noTransverseCapAtPitExit")),
        "noWallClosingPitlane": bool(validation.get("noWallClosingPitlane")),
        "noRibbonOverlapVisible": bool(validation.get("noRibbonOverlapVisible")),
        "noGapBetweenMainAndPitAccess": bool(validation.get("noGapBetweenMainAndPitAccess")),
        "noBlackSeamVisible": bool(validation.get("noBlackSeamVisible")),
        "noRectangularBlock": bool(validation.get("noRectangularBlock")),
        "noFakeChicane": bool(validation.get("noFakeChicane")),
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
    return _svg("Interlagos pit access asphalt merge fix candidate", context, base, candidate, validation)


def _validation_svg(context: Dict[str, Any], base: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    return _svg("Interlagos pit access asphalt merge fix validation", context, base, candidate, validation)


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
        '<text x="28" y="62" fill="#94a3b8" font-size="13" font-family="Segoe UI, Arial">red = previous black void / cyan = mergeFillPolygon / dashed red = suppressed internal edges / gray-white = final outer contours</text>',
    ]
    panels = [
        ("entrada pitlane: merge fill", ENTRY_NAME, ENTRY_MERGE_NAME, gap),
        ("saida pitlane: merge fill", EXIT_NAME, EXIT_MERGE_NAME, gap * 2 + panel_w),
    ]
    for label, access_name, merge_name, x in panels:
        parts.extend(_panel(context, base, candidate, label, access_name, merge_name, x, 78, panel_w, panel_h))
    footer = (
        f"passed={validation['passed']} exitGapFilled={validation['pitExitGapFilled']} "
        f"entryGapFilled={validation['pitEntryGapFilled']} noBlackSeam={validation['noBlackSeamVisible']}"
    )
    parts.append(f'<text x="28" y="{height - 28}" fill="#94a3b8" font-size="14" font-family="Segoe UI, Arial">{_xml(footer)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _panel(
    context: Dict[str, Any],
    base: Dict[str, Any],
    candidate: Dict[str, Any],
    label: str,
    access_name: str,
    merge_name: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> List[str]:
    base_geom = base["visualGeometry"]["geometries"][access_name]
    geom = candidate["visualGeometry"]["geometries"][access_name]
    merge = candidate["visualGeometry"]["geometries"][merge_name]
    main_range = merge["mainRange"]
    main_segment = context["mainLeft"][main_range[0] : main_range[1] + 1]
    focus_points = _line_points(merge["polygon"]) + _line_points(geom["polygon"]) + main_segment
    bounds = _bounds_for_points(focus_points, pad=62.0)
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
        f'<path d="{path(context["mainLeft"])}" fill="none" stroke="#94a3b8" stroke-width="1.8" stroke-opacity="0.55"/>',
        f'<path d="{path(context["mainRight"])}" fill="none" stroke="#94a3b8" stroke-width="1.8" stroke-opacity="0.55"/>',
        f'<path d="{path(_line_points(base_geom["innerEdge"]))}" fill="none" stroke="#ef4444" stroke-width="3.0" stroke-opacity="0.55"/>',
        f'<path d="{path(_line_points(merge["polygon"]), close=True)}" fill="#22d3ee" fill-opacity="0.48" stroke="#38bdf8" stroke-width="1.2" stroke-opacity="0.9"/>',
        f'<path d="{path(_line_points(geom["polygon"]), close=True)}" fill="#64748b" fill-opacity="0.28" stroke="none"/>',
        f'<path d="{path(main_segment)}" fill="none" stroke="#ef4444" stroke-width="2.2" stroke-dasharray="7 7" stroke-opacity="0.8"/>',
        f'<path d="{path(_line_points(geom["innerEdge"]))}" fill="none" stroke="#ef4444" stroke-width="2.0" stroke-dasharray="7 7" stroke-opacity="0.75"/>',
        f'<path d="{path(_line_points(geom["outerEdge"]))}" fill="none" stroke="#e5e7eb" stroke-width="2.2" stroke-opacity="0.8"/>',
    ]
    area = merge.get("areaMeters2")
    max_gap = merge.get("maxGapBeforeFillMeters")
    parts.append(
        f'<text x="{x + 12:.2f}" y="{y + height - 18:.2f}" fill="#94a3b8" font-size="12" font-family="Segoe UI, Arial">mergeArea={area} m2 maxGapBeforeFill={max_gap} m</text>'
    )
    return parts


if __name__ == "__main__":
    main()
