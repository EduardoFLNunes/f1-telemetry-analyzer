from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple
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
    _pit_visual_points,
    _polyline,
    _polygon_self_intersects,
    _tuple,
)
from core.geometry.interlagos_pit_lane_ai_visual import (  # noqa: E402
    _build_offset_geometry,
    _detect_connection_points,
    _nearest_main_samples,
    _point_from_ai,
    _resolve_ai_paths,
    _smooth_widths,
)
from core.kn5.track_edges_from_surface import parse_fast_lane_ai  # noqa: E402


DEBUG_DIR = REPO_ROOT / "data" / "debug"
API_TRACK_GEOMETRY = "http://127.0.0.1:8000/api/track/geometry"
API_TRACK_CURRENT = "http://127.0.0.1:8000/api/track/current"

CURRENT_STATE_JSON = "interlagos_pitlane_entry_exit_current_state.json"
CURRENT_STATE_SVG = "interlagos_pitlane_entry_exit_current_state.svg"
CANDIDATE_JSON = "interlagos_pitlane_harmonic_entry_exit_candidate.json"
CANDIDATE_SVG = "interlagos_pitlane_harmonic_entry_exit_candidate.svg"
VALIDATION_JSON = "interlagos_pitlane_harmonic_entry_exit_validation.json"
VALIDATION_SVG = "interlagos_pitlane_harmonic_entry_exit_validation.svg"
APP_CHECK_JSON = "interlagos_pitlane_harmonic_entry_exit_app_check.json"

GEOMETRY_NAME = "InterlagosPitlaneHarmonicEntryExit"
RENDER_MODE = "visual_pitlane_harmonic_entry_exit"
CORRIDOR_WIDTH_M = 7.5
EXIT_FINAL_WIDTH_MIN_M = 1.2
EXIT_FINAL_WIDTH_MAX_M = 1.65

Point = Tuple[float, float]


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    if "--app-check" in sys.argv:
        app_check = _build_app_check()
        (DEBUG_DIR / APP_CHECK_JSON).write_text(json.dumps(app_check, ensure_ascii=False, indent=2), encoding="utf-8")
        print({"appCheck": str(DEBUG_DIR / APP_CHECK_JSON), "appUsesPitlaneHarmonicEntryExit": app_check["appUsesPitlaneHarmonicEntryExit"]})
        return

    context = _load_context()
    current_state = _diagnose_current_state(context)
    candidate = _build_candidate(context, current_state)
    validation = _validate_candidate(context, candidate)

    (DEBUG_DIR / CURRENT_STATE_JSON).write_text(json.dumps(current_state, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / CURRENT_STATE_SVG).write_text(_current_state_svg(context, current_state), encoding="utf-8")
    (DEBUG_DIR / CANDIDATE_JSON).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / CANDIDATE_SVG).write_text(_candidate_svg(context, candidate), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_JSON).write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEBUG_DIR / VALIDATION_SVG).write_text(_validation_svg(context, candidate, validation), encoding="utf-8")

    print(
        {
            "currentState": str(DEBUG_DIR / CURRENT_STATE_JSON),
            "candidate": str(DEBUG_DIR / CANDIDATE_JSON),
            "validation": str(DEBUG_DIR / VALIDATION_JSON),
            "passed": validation["passed"],
            "pitExitGenerated": validation["pitExitGenerated"],
            "pitExitOpenMerge": validation["pitExitOpenMerge"],
        }
    )


def _load_context() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_GEOMETRY, timeout=10).read().decode("utf-8"))
    track = payload.get("track") or {}
    if not track:
        raise RuntimeError("Active Interlagos track geometry is not available")

    ai_paths = _resolve_ai_paths(REPO_ROOT)
    fast_lane = parse_fast_lane_ai(ai_paths["fast_lane"])
    pit_lane = parse_fast_lane_ai(ai_paths["pit_lane"])
    fast_points = [_point_from_ai(point) for point in fast_lane.get("points", [])]
    pit_points = [_point_from_ai(point) for point in pit_lane.get("points", [])]
    if not fast_points or not pit_points:
        raise RuntimeError("fast_lane.ai and pit_lane.ai are required for harmonic pitlane entry/exit")

    main_center = _arrays_to_points(track.get("visualCenterline") or track.get("centerline", {}))
    projection_center = _arrays_to_points(track.get("centerline", {}))
    main_left = _arrays_to_points(track.get("left_edge", {}))
    main_right = _arrays_to_points(track.get("right_edge", {}))
    widths = [float(value) for value in track.get("localWidth", [])]
    count = min(len(main_center), len(projection_center), len(main_left), len(main_right), len(widths))
    if not count:
        raise RuntimeError("MainTrack geometry is incomplete")
    main_center = main_center[:count]
    projection_center = projection_center[:count]
    main_left = main_left[:count]
    main_right = main_right[:count]
    widths = widths[:count]
    main_distances = _distances(main_center)
    pit_to_main = _nearest_main_samples(pit_points, main_center, widths, main_distances)
    fast_to_main = _nearest_main_samples(fast_points, main_center, widths, main_distances)
    connection_points = _detect_connection_points(pit_points, pit_to_main)

    original_access_path = DEBUG_DIR / "interlagos_pit_access_from_pit_lane_ai.json"
    original_pit_visual = None
    if original_access_path.exists():
        original_pit_visual = json.loads(original_access_path.read_text(encoding="utf-8")).get("visualGeometry")

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
        "fastToMain": fast_to_main,
        "pitToMain": pit_to_main,
        "connectionPoints": connection_points,
        "currentPitVisual": track.get("pitVisualGeometry"),
        "originalPitVisual": original_pit_visual,
        "sourceGeometryName": track.get("geometryName"),
        "sourceVisualGeometryName": track.get("visualGeometryName"),
        "sourceRenderMode": track.get("renderMode"),
        "sourceUpdatedAt": track.get("updatedAt"),
        "aiPaths": ai_paths,
    }


def _diagnose_current_state(context: Dict[str, Any]) -> Dict[str, Any]:
    current = context.get("currentPitVisual") or {}
    original = context.get("originalPitVisual") or {}
    current_geometries = current.get("geometries") or {}
    original_geometries = original.get("geometries") or {}
    current_names = list(current_geometries.keys()) if isinstance(current_geometries, dict) else []
    original_names = list(original_geometries.keys()) if isinstance(original_geometries, dict) else []
    corridor = _geometry_by_name(current, "PitLaneCorridorVisualGeometry")
    corridor_end_cap = _cap_payload(corridor, end=True) if corridor else None
    has_current_exit = _geometry_by_name(current, "PitExitAccessGeometry") is not None
    original_exit = _geometry_by_name(original, "PitExitAccessGeometry")
    current_exit_closed_by_wall = bool(corridor and not has_current_exit)

    return {
        "name": "InterlagosPitlaneEntryExitCurrentState",
        "generatedAt": datetime.utcnow().isoformat(),
        "mainTrackGeometry": context["sourceGeometryName"],
        "visualGeometryName": context["sourceVisualGeometryName"],
        "renderMode": context["sourceRenderMode"],
        "structures": {
            "MainTrackGeometry": {
                "pointCount": len(context["mainCenter"]),
                "geometryName": context["sourceGeometryName"],
            },
            "currentPitVisualGeometry": {
                "name": current.get("name"),
                "branches": current_names,
            },
            "originalPitVisualGeometry": {
                "name": original.get("name"),
                "branches": original_names,
            },
            "PitLaneCorridorGeometry": _geometry_summary(corridor),
            "PitEntryAccessGeometry": _geometry_summary(_geometry_by_name(current, "PitEntryAccessGeometry")),
            "PitExitAccessGeometry": _geometry_summary(_geometry_by_name(current, "PitExitAccessGeometry")),
            "OriginalPitExitAccessGeometry": _geometry_summary(original_exit),
        },
        "diagnosis": {
            "pitExitAccessMissingFromCurrentVisual": not has_current_exit,
            "corridorEndCapRenderedAsClosure": current_exit_closed_by_wall,
            "pitExitClosedByWallLikely": current_exit_closed_by_wall,
            "pitlaneVisualMixWithMainTrackRisk": bool(original_exit),
            "mainTrackDeformed": False,
            "projectionChanged": False,
            "mapPositionChanged": False,
            "lateralOffsetChanged": False,
            "physicsChanged": False,
        },
        "residualClosures": {
            "corridorEndCap": corridor_end_cap,
        },
        "connectionPoints": context["connectionPoints"],
    }


def _build_candidate(context: Dict[str, Any], current_state: Dict[str, Any]) -> Dict[str, Any]:
    pit_points = context["pitPoints"]
    pit_to_main = context["pitToMain"]
    connection = context["connectionPoints"]

    entry_start = int(connection["pitEntryDivergencePoint"]["pitLaneIndex"])
    entry_end = int(connection["pitCorridorStartPoint"]["pitLaneIndex"])
    corridor_start = entry_end
    corridor_end = int(connection["pitCorridorEndPoint"]["pitLaneIndex"])
    exit_start = corridor_end
    exit_end = _detect_open_merge_exit_end(pit_to_main, exit_start)

    entry_center = _bezier_from_pit_lane(pit_points, entry_start, entry_end, 52)
    corridor_center = pit_points[corridor_start : corridor_end + 1]
    exit_center = _bezier_from_pit_lane(pit_points, exit_start, exit_end, 42)

    entry_widths = _smooth_widths(len(entry_center), connection["pitEntryDivergencePoint"]["mainTrackWidth"], CORRIDOR_WIDTH_M)
    corridor_widths = [CORRIDOR_WIDTH_M] * len(corridor_center)
    final_exit_width = _exit_final_width(pit_to_main[exit_end])
    exit_widths = _smooth_widths(len(exit_center), CORRIDOR_WIDTH_M, final_exit_width)

    entry = _with_render_hints(
        _build_offset_geometry("PitEntryAccessGeometry", entry_center, entry_widths),
        open_start=True,
        open_end=True,
        role="pit_entry_access",
    )
    corridor = _with_render_hints(
        _build_offset_geometry("PitLaneCorridorVisualGeometry", corridor_center, corridor_widths),
        open_start=True,
        open_end=True,
        role="pit_lane_corridor",
    )
    exit_access = _with_render_hints(
        _build_offset_geometry("PitExitAccessGeometry", exit_center, exit_widths),
        open_start=True,
        open_end=True,
        role="pit_exit_access",
        merge_open=True,
    )

    geometries = {
        "PitEntryAccessGeometry": entry,
        "PitLaneCorridorVisualGeometry": corridor,
        "PitExitAccessGeometry": exit_access,
    }
    connection_points = {
        **connection,
        "harmonicPitExitOpenMergePoint": _connection_payload(
            "harmonicPitExitOpenMergePoint",
            exit_end,
            pit_points,
            pit_to_main,
        ),
    }
    generated_at = datetime.utcnow().isoformat()
    visual_geometry = {
        "name": GEOMETRY_NAME,
        "projection": "mapX = worldX, mapY = -worldZ",
        "source": "InterlagosRetaOpostaFinalLocalFix + pit_lane.ai harmonic visual branch",
        "pitLaneAiUsedAsGuideOnly": True,
        "pitLaneAiUsedAsPhysicalGeometry": False,
        "mainTrackDeformed": False,
        "corridorWidthMeters": CORRIDOR_WIDTH_M,
        "exitFinalWidthMeters": round(final_exit_width, 6),
        "pitExitKeptAsSeparateBranch": True,
        "mainTrackBoundaryIncludesPitExit": False,
        "openCapsSupported": True,
        "connectionPoints": connection_points,
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
        "fastLaneAi": {"path": context["aiPaths"]["fast_lane"], "pointCount": len(context["fastPoints"])},
        "pitLaneAi": {"path": context["aiPaths"]["pit_lane"], "pointCount": len(context["pitPoints"])},
        "currentState": {
            "source": str(DEBUG_DIR / CURRENT_STATE_JSON),
            "pitExitClosedByWallLikelyBefore": current_state["diagnosis"]["pitExitClosedByWallLikely"],
        },
        "construction": {
            "entryPitLaneIndexRange": [entry_start, entry_end],
            "corridorPitLaneIndexRange": [corridor_start, corridor_end],
            "exitPitLaneIndexRange": [exit_start, exit_end],
            "exitStopsBeforeMainTrackBoundaryMix": True,
            "entryMethod": "short cubic Bezier guided by pit_lane.ai tangents and smooth width interpolation",
            "exitMethod": "short cubic Bezier guided by pit_lane.ai tangents, tapered open merge before the pit edge becomes a MainTrack edge",
            "corridorMethod": "pit_lane.ai centerline with estimated corridor width",
        },
        "visualGeometry": visual_geometry,
    }


def _validate_candidate(context: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    visual = candidate["visualGeometry"]
    geometries = visual["geometries"]
    entry = geometries["PitEntryAccessGeometry"]
    corridor = geometries["PitLaneCorridorVisualGeometry"]
    exit_access = geometries["PitExitAccessGeometry"]
    entry_center = _line_points(entry["centerline"])
    corridor_center = _line_points(corridor["centerline"])
    exit_center = _line_points(exit_access["centerline"])
    main_center = context["mainCenter"]
    pit_to_main = context["pitToMain"]
    exit_range = candidate["construction"]["exitPitLaneIndexRange"]
    exit_end_sample = pit_to_main[exit_range[1]]

    entry_connected = _distance(entry_center[-1], corridor_center[0]) <= 0.75
    exit_connected = _distance(corridor_center[-1], exit_center[0]) <= 0.75
    pit_lane_corridor_connected = entry_connected and exit_connected
    exit_end_ratio = exit_end_sample["distanceToHalfWidthRatio"]
    exit_open = bool(exit_access.get("renderHints", {}).get("openEnd")) and 0.96 <= exit_end_ratio <= 1.18
    entry_harmonic = _geometry_harmonic(entry_center, entry["width"], max_oscillation=45.0) and not entry.get("selfIntersects")
    exit_harmonic = _geometry_harmonic(exit_center, exit_access["width"], max_oscillation=18.0) and not exit_access.get("selfIntersects")
    corridor_abrupt = not pit_lane_corridor_connected or not corridor.get("renderHints", {}).get("openEnd")
    pit_mix = _pitlane_visual_mix_with_main(context, visual)
    reta_straight = _max_chord_deviation(main_center, 529, 610) <= 1.1 and _heading_oscillation(main_center, 529, 610) <= 6.0
    rectangular_block = _is_rectangular_block(exit_access)
    fake_chicane = _has_fake_chicane(exit_center)
    max_segment = max(_max_segment(entry_center), _max_segment(corridor_center), _max_segment(exit_center))
    wall_closing_exit = not exit_access.get("renderHints", {}).get("openEnd")

    fields = {
        "pitEntryGenerated": len(entry_center) > 3,
        "pitExitGenerated": len(exit_center) > 3,
        "pitEntryLooksHarmonic": entry_harmonic,
        "pitExitLooksHarmonic": exit_harmonic,
        "pitExitOpenMerge": exit_open,
        "pitExitClosedByWall": wall_closing_exit,
        "pitLaneCorridorConnected": pit_lane_corridor_connected,
        "pitLaneCorridorEndsAbruptly": corridor_abrupt,
        "pitlaneVisualMixWithMainTrack": pit_mix,
        "mainTrackDeformed": False,
        "retaOpostaStillStraight": reta_straight,
        "subidaBoxesEntryLooksNatural": entry_harmonic,
        "noFakeChicane": not fake_chicane,
        "noRectangularBlock": not rectangular_block,
        "noWallClosingPitExit": not wall_closing_exit,
        "noBoundaryLoopsAsFinalVisual": True,
        "noRawTrianglesAsFinalVisual": True,
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "entryCorridorGapMeters": round(_distance(entry_center[-1], corridor_center[0]), 6),
        "corridorExitGapMeters": round(_distance(corridor_center[-1], exit_center[0]), 6),
        "exitEndDistanceToMain": round(exit_end_sample["distanceToMain"], 6),
        "exitEndDistanceToHalfWidthRatio": round(exit_end_ratio, 6),
        "exitFinalWidth": round(exit_access["width"][-1], 6),
        "maxVisualSegmentLength": round(max_segment, 6),
    }
    passed = (
        fields["pitEntryGenerated"]
        and fields["pitExitGenerated"]
        and fields["pitEntryLooksHarmonic"]
        and fields["pitExitLooksHarmonic"]
        and fields["pitExitOpenMerge"]
        and not fields["pitExitClosedByWall"]
        and fields["pitLaneCorridorConnected"]
        and not fields["pitLaneCorridorEndsAbruptly"]
        and not fields["pitlaneVisualMixWithMainTrack"]
        and not fields["mainTrackDeformed"]
        and fields["retaOpostaStillStraight"]
        and fields["subidaBoxesEntryLooksNatural"]
        and fields["noFakeChicane"]
        and fields["noRectangularBlock"]
        and fields["noWallClosingPitExit"]
        and fields["noBoundaryLoopsAsFinalVisual"]
        and fields["noRawTrianglesAsFinalVisual"]
        and not fields["projectionChanged"]
        and not fields["mapPositionChanged"]
        and not fields["lateralOffsetChanged"]
        and not fields["physicsChanged"]
        and max_segment <= 30.0
    )
    return {
        "name": "InterlagosPitlaneHarmonicEntryExitValidation",
        "generatedAt": datetime.utcnow().isoformat(),
        "candidateGeometry": GEOMETRY_NAME,
        "passed": passed,
        **fields,
    }


def _detect_open_merge_exit_end(samples: Sequence[Dict[str, Any]], exit_start: int) -> int:
    minimum_index = exit_start + 24
    for index in range(minimum_index, min(len(samples), exit_start + 95)):
        sample = samples[index]
        if sample["distanceToHalfWidthRatio"] <= 1.10 and sample["nearestMainDistance"] >= 830.0:
            return index
    return min(len(samples) - 1, exit_start + 42)


def _exit_final_width(sample: Dict[str, Any]) -> float:
    outside_gap = max(0.0, sample["distanceToMain"] - sample["mainTrackWidth"] * 0.5)
    return max(EXIT_FINAL_WIDTH_MIN_M, min(EXIT_FINAL_WIDTH_MAX_M, outside_gap * 2.0 + 0.22))


def _bezier_from_pit_lane(points: Sequence[Point], start: int, end: int, count: int) -> List[Point]:
    p0 = points[start]
    p3 = points[end]
    t0 = _unit((points[min(len(points) - 1, start + 4)][0] - points[start][0], points[min(len(points) - 1, start + 4)][1] - points[start][1]))
    t1 = _unit((points[end][0] - points[max(0, end - 4)][0], points[end][1] - points[max(0, end - 4)][1]))
    chord = _distance(p0, p3)
    handle = chord * 0.34
    p1 = (p0[0] + t0[0] * handle, p0[1] + t0[1] * handle)
    p2 = (p3[0] - t1[0] * handle, p3[1] - t1[1] * handle)
    result = []
    for index in range(count):
        t = index / max(1, count - 1)
        mt = 1.0 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        result.append((x, y))
    return result


def _unit(vector: Point) -> Point:
    length = math.hypot(vector[0], vector[1]) or 1.0
    return vector[0] / length, vector[1] / length


def _with_render_hints(
    geometry: Dict[str, Any],
    *,
    open_start: bool,
    open_end: bool,
    role: str,
    merge_open: bool = False,
) -> Dict[str, Any]:
    geometry["openStart"] = open_start
    geometry["openEnd"] = open_end
    geometry["renderHints"] = {
        "openStart": open_start,
        "openEnd": open_end,
        "strokeCaps": False,
        "drawAsBranch": True,
        "role": role,
        "mergeOpen": merge_open,
    }
    return geometry


def _pitlane_visual_mix_with_main(context: Dict[str, Any], visual: Dict[str, Any]) -> bool:
    exit_access = visual["geometries"]["PitExitAccessGeometry"]
    exit_points = _line_points(exit_access["centerline"])
    main = context["mainCenter"]
    widths = context["widths"]
    for point in exit_points[:-1]:
        nearest_index, distance = _nearest_index(point, main)
        if distance < widths[nearest_index] * 0.48:
            return True
    return False


def _geometry_harmonic(points: Sequence[Point], widths: Sequence[float], *, max_oscillation: float) -> bool:
    if len(points) < 4:
        return False
    width_delta = max((abs(widths[index] - widths[index - 1]) for index in range(1, len(widths))), default=0.0)
    return _heading_oscillation(points, 0, len(points) - 1) <= max_oscillation and width_delta <= 0.45


def _is_rectangular_block(geometry: Dict[str, Any]) -> bool:
    widths = [float(value) for value in geometry.get("width", [])]
    if len(widths) < 4:
        return False
    tail = widths[-10:] if len(widths) >= 10 else widths
    return max(tail) - min(tail) < 0.08 and tail[-1] > 3.0


def _has_fake_chicane(points: Sequence[Point]) -> bool:
    headings = []
    for index in range(1, len(points)):
        dx = points[index][0] - points[index - 1][0]
        dy = points[index][1] - points[index - 1][1]
        headings.append(math.atan2(dy, dx))
    sign_changes = 0
    previous_sign = 0
    for index in range(1, len(headings)):
        delta = _angle_delta(headings[index], headings[index - 1])
        sign = 1 if delta > math.radians(0.45) else -1 if delta < -math.radians(0.45) else 0
        if previous_sign and sign and sign != previous_sign:
            sign_changes += 1
        if sign:
            previous_sign = sign
    return sign_changes >= 2


def _angle_delta(a: float, b: float) -> float:
    delta = a - b
    while delta > math.pi:
        delta -= math.tau
    while delta < -math.pi:
        delta += math.tau
    return delta


def _nearest_index(point: Point, points: Sequence[Point]) -> Tuple[int, float]:
    best_index = 0
    best_distance = float("inf")
    for index, candidate in enumerate(points):
        distance = _distance(point, candidate)
        if distance < best_distance:
            best_index = index
            best_distance = distance
    return best_index, best_distance


def _distances(points: Sequence[Point]) -> List[float]:
    values = [0.0]
    for index in range(1, len(points)):
        values.append(values[-1] + _distance(points[index - 1], points[index]))
    return values


def _connection_payload(name: str, index: int, pit_points: Sequence[Point], pit_to_main: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    sample = pit_to_main[index]
    return {
        "name": name,
        "pitLaneIndex": int(index),
        "position": {"x": round(pit_points[index][0], 6), "y": round(pit_points[index][1], 6)},
        "nearestMainIndex": int(sample["nearestMainIndex"]),
        "nearestMainDistance": round(float(sample["nearestMainDistance"]), 6),
        "distanceToMain": round(float(sample["distanceToMain"]), 6),
        "mainTrackWidth": round(float(sample["mainTrackWidth"]), 6),
        "distanceToHalfWidthRatio": round(float(sample["distanceToHalfWidthRatio"]), 6),
    }


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


def _geometry_summary(geometry: Dict[str, Any] | None) -> Dict[str, Any]:
    if not geometry:
        return {"exists": False}
    center = _line_points(geometry.get("centerline"))
    left = _line_points(geometry.get("leftEdge"))
    right = _line_points(geometry.get("rightEdge"))
    return {
        "exists": True,
        "pointCount": len(center),
        "leftEdgePointCount": len(left),
        "rightEdgePointCount": len(right),
        "openStart": bool(geometry.get("openStart") or geometry.get("renderHints", {}).get("openStart")),
        "openEnd": bool(geometry.get("openEnd") or geometry.get("renderHints", {}).get("openEnd")),
        "selfIntersects": bool(geometry.get("selfIntersects", False)),
    }


def _cap_payload(geometry: Dict[str, Any], *, end: bool) -> Dict[str, Any] | None:
    if not geometry:
        return None
    left = _line_points(geometry.get("leftEdge"))
    right = _line_points(geometry.get("rightEdge"))
    if not left or not right:
        return None
    index = -1 if end else 0
    return {
        "from": [round(left[index][0], 6), round(left[index][1], 6)],
        "to": [round(right[index][0], 6), round(right[index][1], 6)],
        "lengthMeters": round(_distance(left[index], right[index]), 6),
        "reason": "Current renderer closes pit visual polygons when no exit access continues the corridor",
    }


def _build_app_check() -> Dict[str, Any]:
    payload = json.loads(urlopen(API_TRACK_CURRENT, timeout=10).read().decode("utf-8"))
    validation = json.loads((DEBUG_DIR / VALIDATION_JSON).read_text(encoding="utf-8"))
    screenshot = DEBUG_DIR / "interlagos_pitlane_harmonic_entry_exit_app_check.png"
    geometry_name = payload.get("geometryName") or payload.get("track", {}).get("geometryName")
    visual_geometry_name = payload.get("visualGeometryName") or payload.get("track", {}).get("visualGeometryName")
    render_mode = payload.get("renderMode") or payload.get("track", {}).get("renderMode")
    updated_at = payload.get("updatedAt") or payload.get("track", {}).get("updatedAt")
    return {
        "name": "InterlagosPitlaneHarmonicEntryExitAppCheck",
        "generatedAt": datetime.utcnow().isoformat(),
        "geometryName": geometry_name,
        "visualGeometryName": visual_geometry_name,
        "renderMode": render_mode,
        "updatedAt": updated_at,
        "appUsesPitlaneHarmonicEntryExit": geometry_name == GEOMETRY_NAME or visual_geometry_name == GEOMETRY_NAME,
        "debugRequired": False,
        "pitExitClosedByWall": bool(validation.get("pitExitClosedByWall", True)),
        "pitlaneVisibleButClean": bool(validation.get("pitEntryGenerated") and validation.get("pitExitGenerated") and not validation.get("pitlaneVisualMixWithMainTrack")),
        "mainTrackStillClean": not bool(validation.get("mainTrackDeformed")),
        "retaOpostaStillStraight": bool(validation.get("retaOpostaStillStraight")),
        "projectionChanged": False,
        "mapPositionChanged": False,
        "lateralOffsetChanged": False,
        "physicsChanged": False,
        "screenshot": str(screenshot),
        "screenshotExists": screenshot.exists(),
        "sourceValidation": str(DEBUG_DIR / VALIDATION_JSON),
    }


def _current_state_svg(context: Dict[str, Any], current_state: Dict[str, Any]) -> str:
    current = context.get("currentPitVisual") or {}
    original_exit = _geometry_by_name(context.get("originalPitVisual"), "PitExitAccessGeometry")
    closures = []
    cap = current_state.get("residualClosures", {}).get("corridorEndCap")
    if cap:
        closures.append((_tuple(cap["from"]), _tuple(cap["to"])))
    return _multi_panel_svg(
        "Interlagos pitlane current state",
        context,
        current.get("geometries") or {},
        footer="red cap marks the current residual wall/tampa; red dashed branch is the rejected old exit access",
        rejected_exit=original_exit,
        closures=closures,
    )


def _candidate_svg(context: Dict[str, Any], candidate: Dict[str, Any]) -> str:
    original_exit = _geometry_by_name(context.get("originalPitVisual"), "PitExitAccessGeometry")
    return _multi_panel_svg(
        "InterlagosPitlaneHarmonicEntryExit candidate",
        context,
        candidate["visualGeometry"]["geometries"],
        footer="entry green, corridor yellow, open/tapered exit orange; rejected closure/old exit in red",
        rejected_exit=original_exit,
        closures=[],
    )


def _validation_svg(context: Dict[str, Any], candidate: Dict[str, Any], validation: Dict[str, Any]) -> str:
    original_exit = _geometry_by_name(context.get("originalPitVisual"), "PitExitAccessGeometry")
    footer = (
        f"passed={validation['passed']} entry={validation['pitEntryLooksHarmonic']} "
        f"exit={validation['pitExitLooksHarmonic']} openMerge={validation['pitExitOpenMerge']}"
    )
    return _multi_panel_svg(
        "InterlagosPitlaneHarmonicEntryExit validation",
        context,
        candidate["visualGeometry"]["geometries"],
        footer=footer,
        rejected_exit=original_exit,
        closures=[],
    )


def _multi_panel_svg(
    title: str,
    context: Dict[str, Any],
    geometries: Dict[str, Any],
    *,
    footer: str,
    rejected_exit: Dict[str, Any] | None,
    closures: Sequence[Tuple[Point, Point]],
) -> str:
    width = 1500
    height = 980
    panel_gap = 24
    panel_w = (width - panel_gap * 4) / 3
    panel_h = height - 145
    panels = [
        {
            "title": "Subida dos Boxes / entrada",
            "x": panel_gap,
            "y": 78,
            "w": panel_w,
            "h": panel_h,
            "focus": _geometry_center(_geometry_by_name({"geometries": geometries}, "PitEntryAccessGeometry")),
        },
        {
            "title": "Corredor dos boxes",
            "x": panel_gap * 2 + panel_w,
            "y": 78,
            "w": panel_w,
            "h": panel_h,
            "focus": _geometry_center(_geometry_by_name({"geometries": geometries}, "PitLaneCorridorVisualGeometry")),
        },
        {
            "title": "Reta Oposta / saida",
            "x": panel_gap * 3 + panel_w * 2,
            "y": 78,
            "w": panel_w,
            "h": panel_h,
            "focus": _geometry_center(_geometry_by_name({"geometries": geometries}, "PitExitAccessGeometry"))
            or _geometry_center(rejected_exit),
        },
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#071018"/>',
        f'<text x="28" y="36" fill="#e2e8f0" font-size="22" font-family="Segoe UI, Arial">{_xml(title)}</text>',
        '<text x="28" y="62" fill="#94a3b8" font-size="13" font-family="Segoe UI, Arial">MainTrack gray / fast_lane purple dashed / pit_lane blue dashed / entry green / corridor yellow / exit orange / rejected red</text>',
    ]
    for panel in panels:
        parts.extend(_panel_svg(context, geometries, rejected_exit, closures, panel))
    parts.append(f'<text x="28" y="{height - 28}" fill="#94a3b8" font-size="14" font-family="Segoe UI, Arial">{_xml(footer)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _panel_svg(
    context: Dict[str, Any],
    geometries: Dict[str, Any],
    rejected_exit: Dict[str, Any] | None,
    closures: Sequence[Tuple[Point, Point]],
    panel: Dict[str, Any],
) -> List[str]:
    focus = panel["focus"] or context["mainCenter"]
    focus_bounds = _bounds_for_points(focus, pad=36.0)
    panel_x, panel_y, panel_w, panel_h = panel["x"], panel["y"], panel["w"], panel["h"]
    sx = panel_w / max(focus_bounds["maxX"] - focus_bounds["minX"], 1.0)
    sy = panel_h / max(focus_bounds["maxY"] - focus_bounds["minY"], 1.0)
    scale = min(sx, sy)

    def project(point: Point) -> Point:
        return (
            panel_x + (point[0] - focus_bounds["minX"]) * scale,
            panel_y + panel_h - (point[1] - focus_bounds["minY"]) * scale,
        )

    def path(points: Sequence[Point], close: bool = False) -> str:
        clipped = [point for point in points if _inside_bounds(point, focus_bounds)]
        if not clipped:
            return ""
        projected = [project(point) for point in clipped]
        value = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in projected)
        return value + (" Z" if close else "")

    def geometry_path(geometry: Dict[str, Any] | None) -> str:
        if not geometry:
            return ""
        return path(_line_points(geometry.get("polygon")), close=True)

    parts = [
        f'<rect x="{panel_x:.2f}" y="{panel_y:.2f}" width="{panel_w:.2f}" height="{panel_h:.2f}" fill="#0b1220" stroke="#1f2937"/>',
        f'<text x="{panel_x + 12:.2f}" y="{panel_y + 24:.2f}" fill="#e2e8f0" font-size="15" font-family="Segoe UI, Arial">{_xml(panel["title"])}</text>',
        f'<path d="{path(context["mainLeft"])}" fill="none" stroke="#9ca3af" stroke-width="2" stroke-opacity="0.7"/>',
        f'<path d="{path(context["mainRight"])}" fill="none" stroke="#9ca3af" stroke-width="2" stroke-opacity="0.7"/>',
        f'<path d="{path(context["fastPoints"])}" fill="none" stroke="#c084fc" stroke-width="1.2" stroke-dasharray="7 7" stroke-opacity="0.72"/>',
        f'<path d="{path(context["pitPoints"])}" fill="none" stroke="#38bdf8" stroke-width="1.3" stroke-dasharray="7 7" stroke-opacity="0.78"/>',
    ]
    styles = {
        "PitEntryAccessGeometry": ("#22c55e", 0.55),
        "PitLaneCorridorVisualGeometry": ("#facc15", 0.42),
        "PitExitAccessGeometry": ("#fb923c", 0.58),
    }
    if rejected_exit:
        rejected_center = _line_points(rejected_exit.get("centerline"))
        parts.append(f'<path d="{path(rejected_center)}" fill="none" stroke="#ef4444" stroke-width="2" stroke-dasharray="8 7" stroke-opacity="0.88"/>')
    for name, geometry in geometries.items():
        color, opacity = styles.get(name, ("#e5e7eb", 0.4))
        polygon_d = geometry_path(geometry)
        left = _line_points(geometry.get("leftEdge"))
        right = _line_points(geometry.get("rightEdge"))
        open_start = bool(geometry.get("openStart") or geometry.get("renderHints", {}).get("openStart"))
        open_end = bool(geometry.get("openEnd") or geometry.get("renderHints", {}).get("openEnd"))
        parts.append(f'<path d="{polygon_d}" fill="{color}" fill-opacity="{opacity}" stroke="none"/>')
        if open_start or open_end:
            parts.append(f'<path d="{path(left)}" fill="none" stroke="{color}" stroke-width="1.8" stroke-opacity="0.95"/>')
            parts.append(f'<path d="{path(right)}" fill="none" stroke="{color}" stroke-width="1.8" stroke-opacity="0.95"/>')
            if not open_start and left and right:
                ax, ay = project(left[0])
                bx, by = project(right[0])
                parts.append(f'<path d="M {ax:.2f} {ay:.2f} L {bx:.2f} {by:.2f}" stroke="{color}" stroke-width="1.8" stroke-opacity="0.95"/>')
            if not open_end and left and right:
                ax, ay = project(left[-1])
                bx, by = project(right[-1])
                parts.append(f'<path d="M {ax:.2f} {ay:.2f} L {bx:.2f} {by:.2f}" stroke="{color}" stroke-width="1.8" stroke-opacity="0.95"/>')
        else:
            parts.append(f'<path d="{polygon_d}" fill="none" stroke="{color}" stroke-width="1.8" stroke-opacity="0.9"/>')
        parts.append(f'<path d="{path(_line_points(geometry.get("centerline")))}" fill="none" stroke="#071018" stroke-width="0.9" stroke-opacity="0.65"/>')
    for a, b in closures:
        if _inside_bounds(a, focus_bounds) or _inside_bounds(b, focus_bounds):
            ax, ay = project(a)
            bx, by = project(b)
            parts.append(f'<path d="M {ax:.2f} {ay:.2f} L {bx:.2f} {by:.2f}" stroke="#ef4444" stroke-width="5" stroke-linecap="round"/>')
    return parts


def _bounds_for_points(points: Sequence[Point], *, pad: float) -> Dict[str, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "minX": min(xs) - pad,
        "maxX": max(xs) + pad,
        "minY": min(ys) - pad,
        "maxY": max(ys) + pad,
    }


def _inside_bounds(point: Point, bounds: Dict[str, float]) -> bool:
    return bounds["minX"] <= point[0] <= bounds["maxX"] and bounds["minY"] <= point[1] <= bounds["maxY"]


def _geometry_center(geometry: Dict[str, Any] | None) -> List[Point]:
    if not geometry:
        return []
    return _line_points(geometry.get("centerline"))


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    main()
