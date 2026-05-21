"""Generate debug-only MainTrack candidate v2 variants around pit breaks.

The variants use larger anchor margins around the confirmed problem windows and
quintic Hermite interpolation with exterior MainTrack tangents. The script only
writes debug/export artifacts; it does not change runtime or authoritative
geometry, and it never selects a candidate automatically.
"""
from __future__ import annotations

import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"
MAIN_TRACK_JSON = REPO_ROOT / "data" / "cache" / "tracks" / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
PITLANE_MANUAL_JSON = DEBUG_DIR / "interlagos_pitlane_trimmed_manual_05_05.json"

ENTRY_VARIANTS_JSON = DEBUG_DIR / "interlagos_entry_maintrack_candidate_v2_variants.json"
ENTRY_VARIANTS_SVG = DEBUG_DIR / "interlagos_entry_maintrack_candidate_v2_variants.svg"
EXIT_VARIANTS_JSON = DEBUG_DIR / "interlagos_exit_maintrack_candidate_v2_variants.json"
EXIT_VARIANTS_SVG = DEBUG_DIR / "interlagos_exit_maintrack_candidate_v2_variants.svg"
OVERVIEW_SVG = DEBUG_DIR / "interlagos_entry_exit_candidate_v2_overview.svg"

ANCHOR_MARGINS = [20, 35, 50, 75]
ENTRY_BREAK = (1804, 1858)
EXIT_BREAK = (1479, 1549)
PIT_MANUAL_START = {"x": -339.274471, "y": -425.069001}
PIT_MANUAL_END = {"x": -432.446484, "y": -75.929951}

VARIANT_COLORS = {
    20: "#22d3ee",
    35: "#a78bfa",
    50: "#34d399",
    75: "#f97316",
}

Point = Dict[str, float]


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def point_xy(point: Dict[str, Any]) -> Point:
    return {"x": float(point["x"]), "y": float(point.get("y", point.get("z", 0.0)))}


def points_xy(points: Iterable[Dict[str, Any]]) -> List[Point]:
    return [point_xy(point) for point in points or []]


def point_round(point: Point) -> Point:
    return {"x": round(point["x"], 6), "y": round(point["y"], 6)}


def points_round(points: Iterable[Point]) -> List[Point]:
    return [point_round(point) for point in points]


def distance(a: Point, b: Point) -> float:
    return math.hypot(b["x"] - a["x"], b["y"] - a["y"])


def subtract(a: Point, b: Point) -> Point:
    return {"x": a["x"] - b["x"], "y": a["y"] - b["y"]}


def add(a: Point, b: Point) -> Point:
    return {"x": a["x"] + b["x"], "y": a["y"] + b["y"]}


def scale_vector(v: Point, scale: float) -> Point:
    return {"x": v["x"] * scale, "y": v["y"] * scale}


def dot(a: Point, b: Point) -> float:
    return a["x"] * b["x"] + a["y"] * b["y"]


def normalize(v: Point) -> Point:
    length = math.hypot(v["x"], v["y"])
    if length <= 1e-9:
        return {"x": 0.0, "y": 0.0}
    return {"x": v["x"] / length, "y": v["y"] / length}


def angle_between(a: Point, b: Point) -> float:
    na = normalize(a)
    nb = normalize(b)
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(na, nb)))))


def tangent_between(points: List[Point], start_index: int, end_index: int) -> Point:
    start = points[max(0, min(len(points) - 1, start_index))]
    end = points[max(0, min(len(points) - 1, end_index))]
    return normalize(subtract(end, start))


def exterior_tangents(points: List[Point], suspect_start: int, suspect_end: int, anchor_start: int, anchor_end: int, margin: int) -> Tuple[Point, Point]:
    span = max(6, min(24, margin // 2))
    start_back = max(0, anchor_start - span)
    start_forward = min(suspect_start - 1, anchor_start + span)
    end_back = max(suspect_end + 1, anchor_end - span)
    end_forward = min(len(points) - 1, anchor_end + span)
    return tangent_between(points, start_back, start_forward), tangent_between(points, end_back, end_forward)


def quintic_hermite(
    start: Point,
    end: Point,
    tangent_start: Point,
    tangent_end: Point,
    count: int,
    tension: float = 0.68,
) -> List[Point]:
    chord = distance(start, end)
    d0 = scale_vector(normalize(tangent_start), chord * tension)
    d1 = scale_vector(normalize(tangent_end), chord * tension)
    out: List[Point] = []
    for index in range(count):
        t = index / max(count - 1, 1)
        t2 = t * t
        t3 = t2 * t
        t4 = t3 * t
        t5 = t4 * t
        h00 = 1 - 10 * t3 + 15 * t4 - 6 * t5
        h10 = t - 6 * t3 + 8 * t4 - 3 * t5
        h01 = 10 * t3 - 15 * t4 + 6 * t5
        h11 = -4 * t3 + 7 * t4 - 3 * t5
        out.append(
            {
                "x": h00 * start["x"] + h10 * d0["x"] + h01 * end["x"] + h11 * d1["x"],
                "y": h00 * start["y"] + h10 * d0["y"] + h01 * end["y"] + h11 * d1["y"],
            }
        )
    return out


def nearest_point_on_segment(point: Point, a: Point, b: Point) -> Tuple[Point, float]:
    ab = subtract(b, a)
    ap = subtract(point, a)
    denom = dot(ab, ab)
    if denom <= 1e-12:
        return a, distance(point, a)
    t = max(0.0, min(1.0, dot(ap, ab) / denom))
    projected = add(a, scale_vector(ab, t))
    return projected, distance(point, projected)


def nearest_polyline_distance(point: Point, line: List[Point]) -> float:
    return min(nearest_point_on_segment(point, line[index - 1], line[index])[1] for index in range(1, len(line)))


def polyline_length(points: List[Point]) -> float:
    return sum(distance(points[index - 1], points[index]) for index in range(1, len(points)))


def smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)


def width_average(widths: List[float], start: int, end: int) -> float:
    values = [widths[index] for index in range(max(0, start), min(len(widths) - 1, end) + 1)]
    return mean(values) if values else 0.0


def interpolate_widths(width_before: float, width_after: float, count: int) -> List[float]:
    out = []
    for index in range(count):
        t = smoothstep(index / max(count - 1, 1))
        out.append(round(width_before * (1 - t) + width_after * t, 6))
    return out


def segment_tangent(points: List[Point], start: int, end: int) -> Point:
    return normalize(subtract(points[end], points[start]))


def angular_continuity(
    main_center: List[Point],
    candidate: List[Point],
    anchor_start: int,
    anchor_end: int,
) -> Tuple[float, float]:
    span = min(8, max(1, len(candidate) // 8))
    incoming = segment_tangent(main_center, max(0, anchor_start - span), anchor_start)
    candidate_in = segment_tangent(candidate, 0, min(len(candidate) - 1, span))
    candidate_out = segment_tangent(candidate, max(0, len(candidate) - 1 - span), len(candidate) - 1)
    outgoing = segment_tangent(main_center, anchor_end, min(len(main_center) - 1, anchor_end + span))
    return angle_between(incoming, candidate_in), angle_between(candidate_out, outgoing)


def build_variant(
    zone_name: str,
    suspect_start: int,
    suspect_end: int,
    margin: int,
    main_center: List[Point],
    main_width: List[float],
    pit_center: List[Point],
) -> Dict[str, Any]:
    anchor_start = max(0, suspect_start - margin)
    anchor_end = min(len(main_center) - 1, suspect_end + margin)
    original_segment = main_center[anchor_start : anchor_end + 1]
    tangent_start, tangent_end = exterior_tangents(main_center, suspect_start, suspect_end, anchor_start, anchor_end, margin)
    candidate_segment = quintic_hermite(
        main_center[anchor_start],
        main_center[anchor_end],
        tangent_start,
        tangent_end,
        len(original_segment),
    )
    displacements = [distance(original, candidate) for original, candidate in zip(original_segment, candidate_segment)]
    angular_entry, angular_exit = angular_continuity(main_center, candidate_segment, anchor_start, anchor_end)
    width_before = width_average(main_width, anchor_start - 14, anchor_start)
    width_after = width_average(main_width, anchor_end, anchor_end + 14)
    candidate_width = interpolate_widths(width_before, width_after, len(candidate_segment))
    min_pit_distance = min(nearest_polyline_distance(point, pit_center) for point in candidate_segment)
    return {
        "id": f"{zone_name}_candidate_v2_anchor_margin_{margin}",
        "anchorMargin": margin,
        "method": "debug_quintic_hermite_between_distant_maintrack_anchors",
        "pitLaneUsedForCandidate": False,
        "selectedAutomatically": False,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "readyForRuntimeIntegration": False,
        "suspectedStartIndex": suspect_start,
        "suspectedEndIndex": suspect_end,
        "anchorStartIndex": anchor_start,
        "anchorEndIndex": anchor_end,
        "anchorStartPoint": point_round(main_center[anchor_start]),
        "anchorEndPoint": point_round(main_center[anchor_end]),
        "originalSegment": points_round(original_segment),
        "candidateSegment": points_round(candidate_segment),
        "candidateWidth": candidate_width,
        "widthBefore": round(width_before, 6),
        "widthAfter": round(width_after, 6),
        "maxCorrectionDisplacement": round(max(displacements), 6),
        "avgCorrectionDisplacement": round(mean(displacements), 6),
        "continuityAngularEntryDeg": round(angular_entry, 6),
        "continuityAngularExitDeg": round(angular_exit, 6),
        "originalSegmentLength": round(polyline_length(original_segment), 6),
        "candidateSegmentLength": round(polyline_length(candidate_segment), 6),
        "minDistanceToPitLane": round(min_pit_distance, 6),
        "reason": "larger local window with exterior MainTrack tangents; pitlane is not used as a control geometry",
    }


def build_zone_payload(
    zone_name: str,
    suspect_start: int,
    suspect_end: int,
    main_center: List[Point],
    main_width: List[float],
    pit_center: List[Point],
) -> Dict[str, Any]:
    variants = [
        build_variant(zone_name, suspect_start, suspect_end, margin, main_center, main_width, pit_center)
        for margin in ANCHOR_MARGINS
    ]
    return {
        "generatedAt": now_iso(),
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": f"debug_{zone_name}_maintrack_candidate_v2_variants",
        "debugOnly": True,
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
        "anchorMargins": ANCHOR_MARGINS,
        "candidateCount": len(variants),
        "variants": variants,
    }


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


def svg_marker(point: Point, view: Dict[str, float], padding: float, scale: float, color: str, radius: float = 4.2) -> str:
    x, y = map_to_svg(point, view, padding, scale)
    return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{color}" stroke="#050816" stroke-width="1.7"/>'


def svg_canvas(view: Dict[str, float], width_limit: int = 1240, height_limit: int = 900) -> Tuple[float, int, int, int, List[str]]:
    padding = 38
    scale = min((width_limit - padding * 2) / max(view["width"], 1.0), (height_limit - padding * 2) / max(view["height"], 1.0))
    width = int(view["width"] * scale + padding * 2)
    height = int(view["height"] * scale + padding * 2)
    return scale, padding, width, height, [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>MainTrack candidate v2 variants debug-only</title>",
        "<desc>Manual comparison only. MainTrack candidates only; no selected candidate.</desc>",
        '<rect width="100%" height="100%" fill="#050816"/>',
    ]


def write_svg(path: Path, lines: List[str]) -> None:
    path.write_text("\n".join([*lines, "</svg>"]), encoding="utf-8")


def local_main_slice(main_center: List[Point], variants: List[Dict[str, Any]], extra: int = 55) -> List[Point]:
    start = max(0, min(int(variant["anchorStartIndex"]) for variant in variants) - extra)
    end = min(len(main_center) - 1, max(int(variant["anchorEndIndex"]) for variant in variants) + extra)
    return main_center[start : end + 1]


def label_point(points: List[Point]) -> Point:
    return points[len(points) // 2]


def write_zone_svg(output: Path, payload: Dict[str, Any], main_center: List[Point], pit_center: List[Point]) -> None:
    variants = payload["variants"]
    suspect_start = int(payload["suspectedStartIndex"])
    suspect_end = int(payload["suspectedEndIndex"])
    problem_segment = main_center[suspect_start : suspect_end + 1]
    local_main = local_main_slice(main_center, variants)
    all_candidate_points = []
    for variant in variants:
        all_candidate_points.extend(points_xy(variant["candidateSegment"]))
    view = bounds([*local_main, *pit_center, *problem_segment, *all_candidate_points], margin=34.0)
    scale, padding, _, _, lines = svg_canvas(view)
    lines.extend(
        [
            f'<path d="{svg_path(local_main, view, padding, scale)}" fill="none" stroke="#94a3b8" stroke-width="1.35" opacity="0.52"/>',
            f'<path d="{svg_path(pit_center, view, padding, scale)}" fill="none" stroke="#fde047" stroke-width="2.9" opacity="0.94"/>',
            f'<path d="{svg_path(problem_segment, view, padding, scale)}" fill="none" stroke="#ef4444" stroke-width="5.0" opacity="0.96"/>',
        ]
    )
    for variant in variants:
        margin = int(variant["anchorMargin"])
        color = VARIANT_COLORS[margin]
        candidate = points_xy(variant["candidateSegment"])
        lines.append(
            f'<path d="{svg_path(candidate, view, padding, scale)}" fill="none" stroke="{color}" stroke-width="3.4" opacity="0.88"/>'
        )
        lines.append(svg_marker(point_xy(variant["anchorStartPoint"]), view, padding, scale, "#f8fafc", radius=4.7))
        lines.append(svg_marker(point_xy(variant["anchorEndPoint"]), view, padding, scale, "#f8fafc", radius=4.7))
        label = label_point(candidate)
        x, y = map_to_svg(label, view, padding, scale)
        lines.append(svg_text(f"m{margin} max {variant['maxCorrectionDisplacement']:.1f}m", x + 7, y - 7, 10, color))
    write_svg(output, lines)


def write_overview_svg(output: Path, entry_payload: Dict[str, Any], exit_payload: Dict[str, Any], main_center: List[Point], pit_center: List[Point]) -> None:
    entry_problem = main_center[int(entry_payload["suspectedStartIndex"]) : int(entry_payload["suspectedEndIndex"]) + 1]
    exit_problem = main_center[int(exit_payload["suspectedStartIndex"]) : int(exit_payload["suspectedEndIndex"]) + 1]
    view = bounds([*main_center, *pit_center], margin=70.0)
    scale, padding, _, _, lines = svg_canvas(view, width_limit=1320, height_limit=920)
    lines.extend(
        [
            f'<path d="{svg_path(main_center, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.1" opacity="0.62"/>',
            f'<path d="{svg_path(pit_center, view, padding, scale)}" fill="none" stroke="#fde047" stroke-width="2.5" opacity="0.94"/>',
            f'<path d="{svg_path(entry_problem, view, padding, scale)}" fill="none" stroke="#ef4444" stroke-width="4.3" opacity="0.95"/>',
            f'<path d="{svg_path(exit_problem, view, padding, scale)}" fill="none" stroke="#ef4444" stroke-width="4.3" opacity="0.95"/>',
        ]
    )
    for payload in (entry_payload, exit_payload):
        for variant in payload["variants"]:
            margin = int(variant["anchorMargin"])
            color = VARIANT_COLORS[margin]
            candidate = points_xy(variant["candidateSegment"])
            lines.append(
                f'<path d="{svg_path(candidate, view, padding, scale)}" fill="none" stroke="{color}" stroke-width="2.9" opacity="0.76"/>'
            )
    write_svg(output, lines)


def build() -> None:
    main = read_json(MAIN_TRACK_JSON)
    pitlane = read_json(PITLANE_MANUAL_JSON)
    main_center = points_xy(main["centerline"])
    main_width = [float(width) for width in main.get("localWidth", [])]
    pit_center = points_xy(pitlane["pitCenterline"])

    entry_payload = build_zone_payload("entry", ENTRY_BREAK[0], ENTRY_BREAK[1], main_center, main_width, pit_center)
    exit_payload = build_zone_payload("exit", EXIT_BREAK[0], EXIT_BREAK[1], main_center, main_width, pit_center)

    ENTRY_VARIANTS_JSON.write_text(json.dumps(entry_payload, indent=2), encoding="utf-8")
    EXIT_VARIANTS_JSON.write_text(json.dumps(exit_payload, indent=2), encoding="utf-8")
    write_zone_svg(ENTRY_VARIANTS_SVG, entry_payload, main_center, pit_center)
    write_zone_svg(EXIT_VARIANTS_SVG, exit_payload, main_center, pit_center)
    write_overview_svg(OVERVIEW_SVG, entry_payload, exit_payload, main_center, pit_center)

    print(ENTRY_VARIANTS_JSON)
    print(ENTRY_VARIANTS_SVG)
    print(EXIT_VARIANTS_JSON)
    print(EXIT_VARIANTS_SVG)
    print(OVERVIEW_SVG)


if __name__ == "__main__":
    build()
