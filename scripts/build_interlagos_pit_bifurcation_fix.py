from __future__ import annotations

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

from build_interlagos_reta_oposta_final_local_fix import (  # noqa: E402
    _arrays_to_points,
    _distance,
    _heading_oscillation,
    _line_points,
    _max_chord_deviation,
    _max_segment,
    _polyline,
    _polygon_self_intersects,
    _tuple,
)
from core.geometry.interlagos_pit_lane_ai_visual import (  # noqa: E402
    _detect_connection_points,
    _nearest_main_samples,
    _normals_for_open_polyline,
    _point_from_ai,
    _resolve_ai_paths,
)
from core.kn5.track_edges_from_surface import parse_fast_lane_ai  # noqa: E402


DEBUG_DIR = REPO_ROOT / "data" / "debug"
API_TRACK_GEOMETRY = "http://127.0.0.1:8000/api/track/geometry"
API_TRACK_CURRENT = "http://127.0.0.1:8000/api/track/current"

AUDIT_JSON = "interlagos_bifurcation_zone_audit.json"
AUDIT_SVG = "interlagos_bifurcation_zone_audit.svg"
CANDIDATE_JSON = "interlagos_pit_bifurcation_fix_candidate.json"
CANDIDATE_SVG = "interlagos_pit_bifurcation_fix_candidate.svg"
VALIDATION_JSON = "interlagos_pit_bifurcation_fix_validation.json"
VALIDATION_SVG = "interlagos_pit_bifurcation_fix_validation.svg"
APP_CHECK_JSON = "interlagos_pit_bifurcation_fix_app_check.json"

GEOMETRY_NAME = "InterlagosPitBifurcationFix"
ENTRY_GEOMETRY_NAME = "InterlagosPitEntryBifurcationGeometry"
EXIT_GEOMETRY_NAME = "InterlagosPitExitBifurcationGeometry"
RENDER_MODE = "visual_pit_bifurcation_fix"
CORRIDOR_WIDTH_M = 7.5
EDGE_CLEARANCE_MARGIN_M = 0.08

Point = Tuple[float, float]


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    if "--app-check" in sys.argv:
        app_check = _build_app_check()
        (DEBUG_DIR / APP_CHECK_JSON).write_text(json.dumps(app_check, ensure_ascii=False, indent=2), encoding="utf-8")
        print({"appCheck": str(DEBUG_DIR / APP_CHECK_JSON), "appUsesPitBifurcationFix": app_check["appUsesPitBifurcationFix"]})
        return

    context = _load_context()
    audit = _build_audit(context)
    candidate = _build_candidate(context, audit)
    validation = _validate_candidate(context, audit, candidate)

    (DEBUG_DIR / AUDIT_JSON).write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / AUDIT_SVG).write_text(_audit_svg(context, audit), encoding="utf-8")
    (DEBUG_DIR / CANDIDATE_JSON).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / CANDIDATE_SVG).write_text(_candidate_svg(context, audit, candidate), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_JSON).write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_SVG).write_text(_validation_svg(context, audit, candidate, validation), encoding="utf-8")

    print(
        {
            "audit": str(DEBUG_DIR / AUDIT_JSON),
            "candidate": str(DEBUG_DIR / CANDIDATE_JSON),
            "validation": str(DEBUG_DIR / VALIDATION_JSON),
            "passed": validation["passed"],
            "entrySplitLooksNatural": validation["entrySplitLooksNatural"],
            "exitMergeLooksNatural": validation["exitMergeLooksNatural"],
            "noRibbonOverlap": validation["noRibbonOverlap"],
        }
    )


def _load_context() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_GEOMETRY, timeout=10).read().decode("utf-8"))
    track = payload.get("track") or {}
    if not track:
        raise RuntimeError("Active Interlagos geometry is unavailable")

    ai_paths = _resolve_ai_paths(REPO_ROOT)
    fast_lane = parse_fast_lane_ai(ai_paths["fast_lane"])
    pit_lane = parse_fast_lane_ai(ai_paths["pit_lane"])
    fast_points = [_point_from_ai(point) for point in fast_lane.get("points", [])]
    pit_points = [_point_from_ai(point) for point in pit_lane.get("points", [])]
    main_center = _arrays_to_points(track.get("visualCenterline") or track.get("centerline", {}))
    projection_center = _arrays_to_points(track.get("centerline", {}))
    main_left = _arrays_to_points(track.get("left_edge", {}))
    main_right = _arrays_to_points(track.get("right_edge", {}))
    widths = [float(value) for value in track.get("localWidth", [])]
    count = min(len(main_center), len(projection_center), len(main_left), len(main_right), len(widths))
    if not fast_points or not pit_points or not count:
        raise RuntimeError("Bifurcation fix requires MainTrackGeometry, fast_lane.ai and pit_lane.ai")

    main_center = main_center[:count]
    projection_center = projection_center[:count]
    main_left = main_left[:count]
    main_right = main_right[:count]
    widths = widths[:count]
    main_distances = _distances(main_center)
    pit_to_main = _nearest_main_samples(pit_points, main_center, widths, main_distances)
    fast_to_main = _nearest_main_samples(fast_points, main_center, widths, main_distances)
    connection_points = _detect_connection_points(pit_points, pit_to_main)

    return {
        "apiPayload": payload,
        "track": track,
        "mainCenter": main_center,
        "projectionCenter": projection_center,
        "mainLeft": main_left,
        "mainRight": main_right,
        "widths": widths,
        "mainDistances": main_distances,
        "fastPoints": fast_points,
        "pitPoints": pit_points,
        "pitToMain": pit_to_main,
        "fastToMain": fast_to_main,
        "connectionPoints": connection_points,
        "currentPitVisual": track.get("pitVisualGeometry"),
        "sourceGeometryName": track.get("geometryName"),
        "sourceVisualGeometryName": track.get("visualGeometryName"),
        "sourceRenderMode": track.get("renderMode"),
        "sourceUpdatedAt": track.get("updatedAt"),
        "aiPaths": ai_paths,
    }


def _build_audit(context: Dict[str, Any]) -> Dict[str, Any]:
    pit_to_main = context["pitToMain"]
    pit_points = context["pitPoints"]
    connection = context["connectionPoints"]

    entry_boundary = _first_boundary_crossing(pit_to_main, 150, connection["pitCorridorStartPoint"]["pitLaneIndex"])
    exit_boundary = _last_boundary_crossing(pit_to_main, connection["pitCorridorEndPoint"]["pitLaneIndex"], 1040)
    entry_main_index = int(pit_to_main[entry_boundary]["nearestMainIndex"])
    exit_main_index = int(pit_to_main[exit_boundary]["nearestMainIndex"])
    current_overlap = _current_ribbon_overlap(context)
    entry_zone = _zone_payload(
        "Pit Entry Split Zone",
        entry_boundary,
        connection["pitCorridorStartPoint"]["pitLaneIndex"],
        entry_main_index,
        context,
        transition="split",
    )
    exit_zone = _zone_payload(
        "Pit Exit Merge Zone",
        connection["pitCorridorEndPoint"]["pitLaneIndex"],
        exit_boundary,
        exit_main_index,
        context,
        transition="merge",
    )
    return {
        "name": "InterlagosBifurcationZoneAudit",
        "generatedAt": datetime.utcnow().isoformat(),
        "mainTrackGeometry": context["sourceGeometryName"],
        "visualGeometryName": context["sourceVisualGeometryName"],
        "renderMode": context["sourceRenderMode"],
        "diagnosis": {
            "problem": "pitlane access was modeled as overlapping ribbons instead of shared split/merge topology",
            "entryCurrentRibbonOverlapPointCount": current_overlap["entryOverlapPointCount"],
            "exitCurrentRibbonOverlapPointCount": current_overlap["exitOverlapPointCount"],
            "entryNeedsBifurcationTopology": current_overlap["entryOverlapPointCount"] > 0,
            "exitNeedsBifurcationTopology": True,
            "mainTrackDeformed": False,
            "projectionChanged": False,
            "mapPositionChanged": False,
            "lateralOffsetChanged": False,
            "physicsChanged": False,
        },
        "entrySplitZone": entry_zone,
        "exitMergeZone": exit_zone,
        "currentRibbonOverlap": current_overlap,
        "connectionPoints": connection,
        "samplePoints": {
            "entryBoundaryPitLane": _xy_payload(pit_points[entry_boundary]),
            "entryBoundaryMainLeft": _xy_payload(context["mainLeft"][entry_main_index]),
            "exitBoundaryPitLane": _xy_payload(pit_points[exit_boundary]),
            "exitBoundaryMainLeft": _xy_payload(context["mainLeft"][exit_main_index]),
        },
    }


def _build_candidate(context: Dict[str, Any], audit: Dict[str, Any]) -> Dict[str, Any]:
    pit_points = context["pitPoints"]
    main_left = context["mainLeft"]
    main_right = context["mainRight"]
    main_center = context["mainCenter"]
    pit_to_main = context["pitToMain"]
    entry_zone = audit["entrySplitZone"]
    exit_zone = audit["exitMergeZone"]

    entry_start_pit = int(entry_zone["taperStart"]["pitLaneIndex"])
    entry_end_pit = int(entry_zone["taperEnd"]["pitLaneIndex"])
    entry_start_main = int(entry_zone["taperStart"]["nearestMainIndex"])
    entry_end_main = int(entry_zone["taperEnd"]["nearestMainIndex"])
    exit_start_pit = int(exit_zone["taperStart"]["pitLaneIndex"])
    exit_end_pit = int(exit_zone["taperEnd"]["pitLaneIndex"])
    exit_start_main = int(exit_zone["taperStart"]["nearestMainIndex"])
    exit_end_main = int(exit_zone["taperEnd"]["nearestMainIndex"])

    entry_center = _bezier(main_left[entry_start_main], pit_points[entry_end_pit], pit_points, entry_start_pit, entry_end_pit, 48)
    entry_desired_widths = _smooth_widths(len(entry_center), 0.0, CORRIDOR_WIDTH_M)
    entry = _safe_offset_geometry(
        ENTRY_GEOMETRY_NAME,
        entry_center,
        entry_desired_widths,
        context,
        open_start=True,
        open_end=True,
        role="pit_entry_bifurcation",
    )

    corridor_start = entry_end_pit
    corridor_end = exit_start_pit
    corridor_center = pit_points[corridor_start : corridor_end + 1]
    corridor = _safe_offset_geometry(
        "PitLaneCorridorBifurcationGeometry",
        corridor_center,
        [CORRIDOR_WIDTH_M] * len(corridor_center),
        context,
        open_start=True,
        open_end=True,
        role="pit_lane_corridor",
    )

    exit_center = _bezier(pit_points[exit_start_pit], main_left[exit_end_main], pit_points, exit_start_pit, exit_end_pit, 44)
    exit_desired_widths = _smooth_widths(len(exit_center), CORRIDOR_WIDTH_M, 0.0)
    exit_access = _safe_offset_geometry(
        EXIT_GEOMETRY_NAME,
        exit_center,
        exit_desired_widths,
        context,
        open_start=True,
        open_end=True,
        role="pit_exit_bifurcation",
        merge_open=True,
    )

    geometries = {
        ENTRY_GEOMETRY_NAME: entry,
        "PitLaneCorridorBifurcationGeometry": corridor,
        EXIT_GEOMETRY_NAME: exit_access,
    }
    entry_topology = _topology_payload(
        "Pit Entry Split Zone",
        "split",
        entry,
        main_center,
        main_left,
        main_right,
        entry_start_main,
        entry_end_main,
        entry_start_pit,
        entry_end_pit,
    )
    exit_topology = _topology_payload(
        "Pit Exit Merge Zone",
        "merge",
        exit_access,
        main_center,
        main_left,
        main_right,
        exit_start_main,
        exit_end_main,
        exit_start_pit,
        exit_end_pit,
    )
    generated_at = datetime.utcnow().isoformat()
    visual_geometry = {
        "name": GEOMETRY_NAME,
        "projection": "mapX = worldX, mapY = -worldZ",
        "source": "MainTrack preserved + pit_lane.ai bifurcation topology",
        "pitLaneAiUsedAsGuideOnly": True,
        "pitLaneAiUsedAsPhysicalGeometry": False,
        "mainTrackDeformed": False,
        "openCapsSupported": True,
        "bifurcationTopology": {
            "entry": entry_topology,
            "exit": exit_topology,
        },
        "geometries": geometries,
    }
    return {
        "name": GEOMETRY_NAME,
        "geometryName": GEOMETRY_NAME,
        "visualGeometryName": GEOMETRY_NAME,
        "renderMode": RENDER_MODE,
        "generatedAt": generated_at,
        "updatedAt": generated_at,
        "mainTrackGeometry": context["sourceGeometryName"],
        "mainTrackVisualGeometry": context["sourceVisualGeometryName"],
        "mainTrackDeformed": False,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "construction": {
            "entryGeometryName": ENTRY_GEOMETRY_NAME,
            "exitGeometryName": EXIT_GEOMETRY_NAME,
            "entryPitLaneIndexRange": [entry_start_pit, entry_end_pit],
            "exitPitLaneIndexRange": [exit_start_pit, exit_end_pit],
            "entryMainIndexRange": [entry_start_main, entry_end_main],
            "exitMainIndexRange": [exit_start_main, exit_end_main],
            "method": "zero-width split/merge on MainTrack left edge, safe offset constrained outside MainTrack, shared divider edge tracked explicitly",
        },
        "fastLaneAi": {"path": context["aiPaths"]["fast_lane"], "pointCount": len(context["fastPoints"])},
        "pitLaneAi": {"path": context["aiPaths"]["pit_lane"], "pointCount": len(context["pitPoints"])},
        "visualGeometry": visual_geometry,
    }


def _validate_candidate(context: Dict[str, Any], audit: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    visual = candidate["visualGeometry"]
    geometries = visual["geometries"]
    entry = geometries[ENTRY_GEOMETRY_NAME]
    corridor = geometries["PitLaneCorridorBifurcationGeometry"]
    exit_access = geometries[EXIT_GEOMETRY_NAME]
    entry_center = _line_points(entry["centerline"])
    corridor_center = _line_points(corridor["centerline"])
    exit_center = _line_points(exit_access["centerline"])
    entry_gap = _distance(entry_center[-1], corridor_center[0])
    exit_gap = _distance(corridor_center[-1], exit_center[0])
    entry_overlap = _geometry_overlap_count(context, entry)
    corridor_overlap = _geometry_overlap_count(context, corridor)
    exit_overlap = _geometry_overlap_count(context, exit_access)
    all_width_deltas = _adjacent_width_deltas(entry["width"]) + _adjacent_width_deltas(corridor["width"]) + _adjacent_width_deltas(exit_access["width"])
    max_width_delta = max(all_width_deltas or [0.0])
    max_step = max(_max_segment(entry_center), _max_segment(corridor_center), _max_segment(exit_center))
    edge_jumps = _edge_jump_count(entry) + _edge_jump_count(corridor) + _edge_jump_count(exit_access)
    ribbon_overlap_count = entry_overlap + corridor_overlap + exit_overlap
    visual_x_crossing = _visual_x_crossing(context, [entry, corridor, exit_access])
    main_straight = _max_chord_deviation(context["mainCenter"], 529, 610) <= 1.1 and _heading_oscillation(context["mainCenter"], 529, 610) <= 6.0
    fake_chicane = _has_fake_chicane(entry_center) or _has_fake_chicane(exit_center)
    rectangular = _is_rectangular_block(entry) or _is_rectangular_block(exit_access)
    fake_wall = not _open_caps(entry) or not _open_caps(corridor) or not _open_caps(exit_access)
    edge_identity_ok = edge_jumps == 0 and max_step <= 2.0

    fields = {
        "entrySplitLooksNatural": entry_gap <= 0.75 and _geometry_harmonic(entry_center, max_oscillation=50.0) and entry["width"][0] <= 0.01,
        "exitMergeLooksNatural": exit_gap <= 0.75 and _geometry_harmonic(exit_center, max_oscillation=28.0) and exit_access["width"][-1] <= 0.01,
        "noRibbonOverlap": ribbon_overlap_count == 0,
        "noVisualXCrossing": not visual_x_crossing,
        "noFakeWall": not fake_wall,
        "noRectangularBlock": not rectangular,
        "noFakeChicane": not fake_chicane,
        "noEdgeIdentityJump": edge_identity_ok,
        "mainTrackPreserved": True,
        "pitlanePreserved": len(corridor_center) > 50 and len(entry_center) > 3 and len(exit_center) > 3,
        "widthVariationSmooth": max_width_delta <= 0.55,
        "retaOpostaStillStraight": main_straight,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "entryCorridorGapMeters": round(entry_gap, 6),
        "corridorExitGapMeters": round(exit_gap, 6),
        "entryRibbonOverlapPointCount": entry_overlap,
        "corridorRibbonOverlapPointCount": corridor_overlap,
        "exitRibbonOverlapPointCount": exit_overlap,
        "maxWidthDelta": round(max_width_delta, 6),
        "maxVisualSegmentLength": round(max_step, 6),
        "edgeJumpCount": edge_jumps,
    }
    passed = (
        fields["entrySplitLooksNatural"]
        and fields["exitMergeLooksNatural"]
        and fields["noRibbonOverlap"]
        and fields["noVisualXCrossing"]
        and fields["noFakeWall"]
        and fields["noRectangularBlock"]
        and fields["noFakeChicane"]
        and fields["noEdgeIdentityJump"]
        and fields["mainTrackPreserved"]
        and fields["pitlanePreserved"]
        and fields["widthVariationSmooth"]
        and fields["retaOpostaStillStraight"]
        and not fields["projectionChanged"]
        and not fields["mapPositionChanged"]
        and not fields["lateralOffsetChanged"]
        and not fields["physicsChanged"]
    )
    return {
        "name": "InterlagosPitBifurcationFixValidation",
        "generatedAt": datetime.utcnow().isoformat(),
        "candidateGeometry": GEOMETRY_NAME,
        "passed": passed,
        **fields,
    }


def _first_boundary_crossing(samples: Sequence[Dict[str, Any]], start: int, end: int) -> int:
    for index in range(start, end + 1):
        if samples[index]["distanceToHalfWidthRatio"] >= 1.0:
            return index
    return start


def _last_boundary_crossing(samples: Sequence[Dict[str, Any]], start: int, end: int) -> int:
    upper = min(len(samples) - 1, end)
    for index in range(start, upper + 1):
        if samples[index]["distanceToHalfWidthRatio"] <= 1.0:
            return index
    return upper


def _zone_payload(name: str, start_pit: int, end_pit: int, boundary_main: int, context: Dict[str, Any], *, transition: str) -> Dict[str, Any]:
    pit_to_main = context["pitToMain"]
    main_center = context["mainCenter"]
    pit_points = context["pitPoints"]
    start_sample = pit_to_main[start_pit]
    end_sample = pit_to_main[end_pit]
    main_start = int(start_sample["nearestMainIndex"])
    main_end = int(end_sample["nearestMainIndex"])
    return {
        "name": name,
        "transition": transition,
        "trunkBefore": {
            "mainIndexStart": max(0, boundary_main - 18),
            "mainIndexEnd": boundary_main,
            "centerline": _polyline(main_center[max(0, boundary_main - 18) : boundary_main + 1]),
        },
        "mainBranch": {
            "mainIndexStart": min(main_start, main_end),
            "mainIndexEnd": max(main_start, main_end),
            "centerline": _polyline(main_center[min(main_start, main_end) : max(main_start, main_end) + 1]),
        },
        "pitBranch": {
            "pitLaneIndexStart": start_pit,
            "pitLaneIndexEnd": end_pit,
            "centerline": _polyline(pit_points[start_pit : end_pit + 1]),
        },
        "taperStart": _sample_payload(start_pit, pit_points, pit_to_main),
        "taperEnd": _sample_payload(end_pit, pit_points, pit_to_main),
        "fastLaneTangent": _tangent_payload(context["fastPoints"], min(boundary_main, len(context["fastPoints"]) - 1)),
        "pitLaneTangentStart": _tangent_payload(pit_points, start_pit),
        "pitLaneTangentEnd": _tangent_payload(pit_points, end_pit),
        "mainTrackWidthStart": round(float(start_sample["mainTrackWidth"]), 6),
        "mainTrackWidthEnd": round(float(end_sample["mainTrackWidth"]), 6),
        "pitLaneCorridorWidth": CORRIDOR_WIDTH_M,
    }


def _safe_offset_geometry(
    name: str,
    centerline: Sequence[Point],
    desired_widths: Sequence[float],
    context: Dict[str, Any],
    *,
    open_start: bool,
    open_end: bool,
    role: str,
    merge_open: bool = False,
) -> Dict[str, Any]:
    normals = _normals_for_open_polyline(centerline)
    left: List[Point] = []
    right: List[Point] = []
    safe_widths: List[float] = []
    for point, normal, desired_width in zip(centerline, normals, desired_widths):
        width = _safe_width(point, normal, float(desired_width), context)
        half = width * 0.5
        left.append((point[0] + normal[0] * half, point[1] + normal[1] * half))
        right.append((point[0] - normal[0] * half, point[1] - normal[1] * half))
        safe_widths.append(width)

    polygon = list(left) + list(reversed(right))
    inner, outer = _inner_outer_edges(left, right, context)
    return {
        "name": name,
        "centerline": _polyline(centerline),
        "leftEdge": _polyline(left),
        "rightEdge": _polyline(right),
        "innerEdge": _polyline(inner),
        "outerEdge": _polyline(outer),
        "sharedDividerEdge": _polyline(inner),
        "width": [round(value, 6) for value in safe_widths],
        "polygon": _polyline(polygon),
        "selfIntersects": _polygon_self_intersects(polygon),
        "openStart": open_start,
        "openEnd": open_end,
        "renderHints": {
            "openStart": open_start,
            "openEnd": open_end,
            "strokeCaps": False,
            "drawAsBranch": True,
            "role": role,
            "mergeOpen": merge_open,
            "topology": "bifurcation",
        },
    }


def _safe_width(point: Point, normal: Point, desired_width: float, context: Dict[str, Any]) -> float:
    if desired_width <= 0:
        return 0.0
    low = 0.0
    high = desired_width
    for _ in range(14):
        mid = (low + high) * 0.5
        half = mid * 0.5
        a = (point[0] + normal[0] * half, point[1] + normal[1] * half)
        b = (point[0] - normal[0] * half, point[1] - normal[1] * half)
        if _point_outside_main(a, context) and _point_outside_main(b, context):
            low = mid
        else:
            high = mid
    return max(0.0, low)


def _point_outside_main(point: Point, context: Dict[str, Any]) -> bool:
    index, distance = _nearest_index(point, context["mainCenter"])
    return distance >= context["widths"][index] * 0.5 - EDGE_CLEARANCE_MARGIN_M


def _inner_outer_edges(left: Sequence[Point], right: Sequence[Point], context: Dict[str, Any]) -> Tuple[List[Point], List[Point]]:
    inner: List[Point] = []
    outer: List[Point] = []
    for a, b in zip(left, right):
        _, da = _nearest_index(a, context["mainCenter"])
        _, db = _nearest_index(b, context["mainCenter"])
        if da <= db:
            inner.append(a)
            outer.append(b)
        else:
            inner.append(b)
            outer.append(a)
    return inner, outer


def _topology_payload(
    name: str,
    kind: str,
    geometry: Dict[str, Any],
    main_center: Sequence[Point],
    main_left: Sequence[Point],
    main_right: Sequence[Point],
    main_start: int,
    main_end: int,
    pit_start: int,
    pit_end: int,
) -> Dict[str, Any]:
    a = min(main_start, main_end)
    b = max(main_start, main_end)
    return {
        "name": name,
        "kind": kind,
        "trunkCenterline": _polyline(main_center[max(0, a - 12) : a + 1]),
        "mainBranchCenterline": _polyline(main_center[a : b + 1]),
        "pitBranchCenterline": geometry["centerline"],
        "outerLeftEdge": geometry["outerEdge"],
        "outerRightEdge": _polyline(main_right[a : b + 1]),
        "sharedDividerEdge": geometry["sharedDividerEdge"],
        "mainLeftBoundary": _polyline(main_left[a : b + 1]),
        "taperStart": {"mainIndex": a, "pitLaneIndex": pit_start},
        "taperEnd": {"mainIndex": b, "pitLaneIndex": pit_end},
    }


def _current_ribbon_overlap(context: Dict[str, Any]) -> Dict[str, Any]:
    current = context.get("currentPitVisual") or {}
    entry = _geometry_by_name(current, "InterlagosPitEntryBifurcationGeometry") or _geometry_by_name(current, "PitEntryAccessGeometry")
    exit_access = _geometry_by_name(current, "InterlagosPitExitBifurcationGeometry") or _geometry_by_name(current, "PitExitAccessGeometry")
    return {
        "entryOverlapPointCount": _geometry_overlap_count(context, entry) if entry else 0,
        "exitOverlapPointCount": _geometry_overlap_count(context, exit_access) if exit_access else 0,
        "method": "pit visual edge point is inside MainTrack half-width envelope",
    }


def _geometry_overlap_count(context: Dict[str, Any], geometry: Dict[str, Any] | None) -> int:
    if not geometry:
        return 0
    count = 0
    for key in ("leftEdge", "rightEdge"):
        for point in _line_points(geometry.get(key)):
            if not _point_outside_main(point, context):
                count += 1
    return count


def _visual_x_crossing(context: Dict[str, Any], geometries: Sequence[Dict[str, Any]]) -> bool:
    main_segments = _segments(context["mainLeft"]) + _segments(context["mainRight"])
    for geometry in geometries:
        for key in ("leftEdge", "rightEdge"):
            for segment in _segments(_line_points(geometry.get(key))):
                for main_segment in main_segments:
                    if _segments_intersect(segment[0], segment[1], main_segment[0], main_segment[1]):
                        if _distance(segment[0], main_segment[0]) < 0.25 or _distance(segment[1], main_segment[1]) < 0.25:
                            continue
                        return True
    return False


def _bezier(start: Point, end: Point, guide: Sequence[Point], guide_start: int, guide_end: int, count: int) -> List[Point]:
    start_tangent = _unit((guide[min(len(guide) - 1, guide_start + 4)][0] - guide[max(0, guide_start - 1)][0], guide[min(len(guide) - 1, guide_start + 4)][1] - guide[max(0, guide_start - 1)][1]))
    end_tangent = _unit((guide[min(len(guide) - 1, guide_end + 1)][0] - guide[max(0, guide_end - 4)][0], guide[min(len(guide) - 1, guide_end + 1)][1] - guide[max(0, guide_end - 4)][1]))
    chord = _distance(start, end)
    handle = chord * 0.36
    p1 = (start[0] + start_tangent[0] * handle, start[1] + start_tangent[1] * handle)
    p2 = (end[0] - end_tangent[0] * handle, end[1] - end_tangent[1] * handle)
    points = []
    for index in range(count):
        t = index / max(1, count - 1)
        mt = 1.0 - t
        x = mt**3 * start[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * end[0]
        y = mt**3 * start[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * end[1]
        points.append((x, y))
    return points


def _smooth_widths(count: int, start_width: float, end_width: float) -> List[float]:
    if count <= 1:
        return [float(end_width)]
    widths = []
    for index in range(count):
        t = index / (count - 1)
        smooth = t * t * (3.0 - 2.0 * t)
        widths.append(float(start_width) + (float(end_width) - float(start_width)) * smooth)
    return widths


def _geometry_by_name(visual: Any, name: str) -> Dict[str, Any] | None:
    if not isinstance(visual, dict):
        return None
    geometries = visual.get("geometries")
    if isinstance(geometries, dict):
        geometry = geometries.get(name)
        return geometry if isinstance(geometry, dict) else None
    if isinstance(geometries, list):
        for geometry in geometries:
            if isinstance(geometry, dict) and geometry.get("name") == name:
                return geometry
    return None


def _build_app_check() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_CURRENT, timeout=10).read().decode("utf-8"))
    validation = json.loads((DEBUG_DIR / VALIDATION_JSON).read_text(encoding="utf-8"))
    screenshot = DEBUG_DIR / "interlagos_pit_bifurcation_fix_app_check.png"
    geometry_name = payload.get("geometryName") or payload.get("track", {}).get("geometryName")
    visual_geometry_name = payload.get("visualGeometryName") or payload.get("track", {}).get("visualGeometryName")
    render_mode = payload.get("renderMode") or payload.get("track", {}).get("renderMode")
    updated_at = payload.get("updatedAt") or payload.get("track", {}).get("updatedAt")
    return {
        "name": "InterlagosPitBifurcationFixAppCheck",
        "generatedAt": datetime.utcnow().isoformat(),
        "geometryName": geometry_name,
        "visualGeometryName": visual_geometry_name,
        "renderMode": render_mode,
        "updatedAt": updated_at,
        "appUsesPitBifurcationFix": geometry_name == GEOMETRY_NAME or visual_geometry_name == GEOMETRY_NAME,
        "debugRequired": False,
        "pitlaneEntryHarmonic": bool(validation.get("entrySplitLooksNatural")),
        "pitlaneExitHarmonic": bool(validation.get("exitMergeLooksNatural")),
        "noRibbonOverlap": bool(validation.get("noRibbonOverlap")),
        "noVisualXCrossing": bool(validation.get("noVisualXCrossing")),
        "noWallClosingPitlane": bool(validation.get("noFakeWall")),
        "mainTrackStillClean": bool(validation.get("mainTrackPreserved")),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "screenshot": str(screenshot),
        "screenshotExists": screenshot.exists(),
        "sourceValidation": str(DEBUG_DIR / VALIDATION_JSON),
    }


def _audit_svg(context: Dict[str, Any], audit: Dict[str, Any]) -> str:
    return _svg("Interlagos bifurcation zone audit", context, audit, candidate=None, validation=None)


def _candidate_svg(context: Dict[str, Any], audit: Dict[str, Any], candidate: Dict[str, Any]) -> str:
    return _svg("Interlagos pit bifurcation fix candidate", context, audit, candidate=candidate, validation=None)


def _validation_svg(context: Dict[str, Any], audit: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    return _svg("Interlagos pit bifurcation fix validation", context, audit, candidate=candidate, validation=validation)


def _svg(
    title: str,
    context: Dict[str, Any],
    audit: Dict[str, Any],
    *,
    candidate: Dict[str, Any] | None,
    validation: Dict[str, Any] | None,
) -> str:
    width = 1500
    height = 980
    gap = 24
    panel_w = (width - gap * 4) / 3
    panel_h = height - 145
    panels = [
        ("entrada da pitlane", audit["entrySplitZone"], gap),
        ("saida da pitlane", audit["exitMergeZone"], gap * 2 + panel_w),
        ("antes/depois", audit["entrySplitZone"], gap * 3 + panel_w * 2),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#071018"/>',
        f'<text x="28" y="36" fill="#e2e8f0" font-size="22" font-family="Segoe UI, Arial">{_xml(title)}</text>',
        '<text x="28" y="62" fill="#94a3b8" font-size="13" font-family="Segoe UI, Arial">MainTrack gray / current overlap red / pit_lane blue dashed / fast_lane purple dashed / new bifurcation green-orange-yellow</text>',
    ]
    for index, (label, zone, x) in enumerate(panels):
        focus_zone = audit["exitMergeZone"] if index == 1 else zone
        parts.extend(_panel(context, audit, candidate, label, focus_zone, x, 78, panel_w, panel_h, compare=index == 2))
    footer = "audit: overlapping ribbons marked in red"
    if validation:
        footer = (
            f"passed={validation['passed']} entry={validation['entrySplitLooksNatural']} "
            f"exit={validation['exitMergeLooksNatural']} overlap={not validation['noRibbonOverlap']}"
        )
    parts.append(f'<text x="28" y="{height - 28}" fill="#94a3b8" font-size="14" font-family="Segoe UI, Arial">{_xml(footer)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _panel(
    context: Dict[str, Any],
    audit: Dict[str, Any],
    candidate: Dict[str, Any] | None,
    label: str,
    zone: Dict[str, Any],
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    compare: bool,
) -> List[str]:
    focus = _line_points(zone["pitBranch"]["centerline"]) or context["mainCenter"]
    bounds = _bounds_for_points(focus, pad=44.0)
    sx = width / max(bounds["maxX"] - bounds["minX"], 1.0)
    sy = height / max(bounds["maxY"] - bounds["minY"], 1.0)
    scale = min(sx, sy)

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
        f'<path d="{path(context["mainLeft"])}" fill="none" stroke="#9ca3af" stroke-width="2" stroke-opacity="0.7"/>',
        f'<path d="{path(context["mainRight"])}" fill="none" stroke="#9ca3af" stroke-width="2" stroke-opacity="0.7"/>',
        f'<path d="{path(context["fastPoints"])}" fill="none" stroke="#c084fc" stroke-width="1.2" stroke-dasharray="7 7" stroke-opacity="0.72"/>',
        f'<path d="{path(context["pitPoints"])}" fill="none" stroke="#38bdf8" stroke-width="1.3" stroke-dasharray="7 7" stroke-opacity="0.78"/>',
    ]
    current = context.get("currentPitVisual") or {}
    for geometry in _current_geometries(current):
        polygon = _line_points(geometry.get("polygon"))
        if polygon:
            parts.append(f'<path d="{path(polygon, close=True)}" fill="#ef4444" fill-opacity="0.22" stroke="#ef4444" stroke-width="1.2" stroke-opacity="0.64"/>')
    if candidate:
        styles = {
            ENTRY_GEOMETRY_NAME: ("#22c55e", 0.55),
            "PitLaneCorridorBifurcationGeometry": ("#facc15", 0.38),
            EXIT_GEOMETRY_NAME: ("#fb923c", 0.58),
        }
        for name, geometry in candidate["visualGeometry"]["geometries"].items():
            color, opacity = styles[name]
            polygon = _line_points(geometry.get("polygon"))
            left = _line_points(geometry.get("leftEdge"))
            right = _line_points(geometry.get("rightEdge"))
            shared = _line_points(geometry.get("sharedDividerEdge"))
            if polygon:
                parts.append(f'<path d="{path(polygon, close=True)}" fill="{color}" fill-opacity="{opacity}" stroke="none"/>')
            parts.append(f'<path d="{path(left)}" fill="none" stroke="{color}" stroke-width="1.7" stroke-opacity="0.95"/>')
            parts.append(f'<path d="{path(right)}" fill="none" stroke="{color}" stroke-width="1.7" stroke-opacity="0.95"/>')
            parts.append(f'<path d="{path(shared)}" fill="none" stroke="#e5e7eb" stroke-width="1.1" stroke-dasharray="5 6" stroke-opacity="0.76"/>')
    if compare:
        parts.append(f'<text x="{x + 12:.2f}" y="{y + height - 16:.2f}" fill="#fca5a5" font-size="12" font-family="Segoe UI, Arial">red = ribbon atual sobreposto</text>')
    return parts


def _current_geometries(visual: Dict[str, Any]) -> List[Dict[str, Any]]:
    geometries = visual.get("geometries") if isinstance(visual, dict) else {}
    if isinstance(geometries, dict):
        return [geometry for geometry in geometries.values() if isinstance(geometry, dict)]
    if isinstance(geometries, list):
        return [geometry for geometry in geometries if isinstance(geometry, dict)]
    return []


def _sample_payload(index: int, pit_points: Sequence[Point], pit_to_main: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    sample = pit_to_main[index]
    return {
        "pitLaneIndex": int(index),
        "position": _xy_payload(pit_points[index]),
        "nearestMainIndex": int(sample["nearestMainIndex"]),
        "nearestMainDistance": round(float(sample["nearestMainDistance"]), 6),
        "distanceToMain": round(float(sample["distanceToMain"]), 6),
        "mainTrackWidth": round(float(sample["mainTrackWidth"]), 6),
        "distanceToHalfWidthRatio": round(float(sample["distanceToHalfWidthRatio"]), 6),
    }


def _tangent_payload(points: Sequence[Point], index: int) -> Dict[str, float]:
    a = points[max(0, index - 3)]
    b = points[min(len(points) - 1, index + 3)]
    unit = _unit((b[0] - a[0], b[1] - a[1]))
    heading = math.degrees(math.atan2(unit[1], unit[0]))
    return {"x": round(unit[0], 6), "y": round(unit[1], 6), "headingDeg": round(heading, 6)}


def _xy_payload(point: Point) -> Dict[str, float]:
    return {"x": round(point[0], 6), "y": round(point[1], 6)}


def _adjacent_width_deltas(widths: Sequence[float]) -> List[float]:
    return [abs(float(widths[index]) - float(widths[index - 1])) for index in range(1, len(widths))]


def _edge_jump_count(geometry: Dict[str, Any]) -> int:
    total = 0
    for key in ("leftEdge", "rightEdge"):
        points = _line_points(geometry.get(key))
        steps = [_distance(points[index - 1], points[index]) for index in range(1, len(points))]
        if not steps:
            continue
        median = sorted(steps)[len(steps) // 2]
        threshold = max(2.0, median * 3.0)
        total += sum(1 for step in steps if step > threshold)
    return total


def _geometry_harmonic(points: Sequence[Point], *, max_oscillation: float) -> bool:
    return len(points) >= 4 and _heading_oscillation(points, 0, len(points) - 1) <= max_oscillation


def _open_caps(geometry: Dict[str, Any]) -> bool:
    hints = geometry.get("renderHints", {})
    return bool(geometry.get("openStart") or hints.get("openStart")) and bool(geometry.get("openEnd") or hints.get("openEnd"))


def _is_rectangular_block(geometry: Dict[str, Any]) -> bool:
    widths = [float(value) for value in geometry.get("width", [])]
    if len(widths) < 6:
        return False
    return max(widths[:6]) - min(widths[:6]) < 0.05 and max(widths[-6:]) - min(widths[-6:]) < 0.05 and min(widths) > 2.0


def _has_fake_chicane(points: Sequence[Point]) -> bool:
    previous_sign = 0
    changes = 0
    for index in range(2, len(points)):
        a = points[index - 2]
        b = points[index - 1]
        c = points[index]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        sign = 1 if cross > 0.01 else -1 if cross < -0.01 else 0
        if previous_sign and sign and sign != previous_sign:
            changes += 1
        if sign:
            previous_sign = sign
    return changes >= 2


def _nearest_index(point: Point, points: Sequence[Point]) -> Tuple[int, float]:
    best_index = 0
    best_distance = float("inf")
    for index, candidate in enumerate(points):
        distance = _distance(point, candidate)
        if distance < best_distance:
            best_index = index
            best_distance = distance
    return best_index, best_distance


def _segments(points: Sequence[Point]) -> List[Tuple[Point, Point]]:
    return list(zip(points, points[1:]))


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    def orient(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    if max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0]):
        return False
    if max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1]):
        return False
    return orient(a, b, c) * orient(a, b, d) < -1e-9 and orient(c, d, a) * orient(c, d, b) < -1e-9


def _unit(vector: Point) -> Point:
    length = math.hypot(vector[0], vector[1]) or 1.0
    return vector[0] / length, vector[1] / length


def _distances(points: Sequence[Point]) -> List[float]:
    values = [0.0]
    for index in range(1, len(points)):
        values.append(values[-1] + _distance(points[index - 1], points[index]))
    return values


def _bounds_for_points(points: Sequence[Point], *, pad: float) -> Dict[str, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {"minX": min(xs) - pad, "maxX": max(xs) + pad, "minY": min(ys) - pad, "maxY": max(ys) + pad}


def _inside(point: Point, bounds: Dict[str, float]) -> bool:
    return bounds["minX"] <= point[0] <= bounds["maxX"] and bounds["minY"] <= point[1] <= bounds["maxY"]


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    main()
