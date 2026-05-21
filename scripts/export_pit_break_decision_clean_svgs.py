"""Render clean debug-only SVGs for manual pit break decisions.

Reads existing analysis/candidate artifacts and writes visualization-only SVGs.
It does not generate candidates, change runtime state, or mutate authoritative
geometry.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"
MAIN_TRACK_JSON = REPO_ROOT / "data" / "cache" / "tracks" / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
PITLANE_MANUAL_JSON = DEBUG_DIR / "interlagos_pitlane_trimmed_manual_05_05.json"
ENTRY_CANDIDATE_JSON = DEBUG_DIR / "interlagos_maintrack_entry_zone_candidate.json"
EXIT_CANDIDATE_JSON = DEBUG_DIR / "interlagos_maintrack_exit_zone_candidate_v2.json"

ENTRY_CLEAN_SVG = DEBUG_DIR / "interlagos_entry_break_decision_clean.svg"
EXIT_CLEAN_SVG = DEBUG_DIR / "interlagos_exit_break_decision_clean.svg"
OVERVIEW_CLEAN_SVG = DEBUG_DIR / "interlagos_entry_exit_break_decision_overview_clean.svg"

PIT_MANUAL_START = {"x": -339.274471, "y": -425.069001}
PIT_MANUAL_END = {"x": -432.446484, "y": -75.929951}

Point = Dict[str, float]


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def point_xy(point: Dict[str, Any]) -> Point:
    return {"x": float(point["x"]), "y": float(point.get("y", point.get("z", 0.0)))}


def points_xy(points: Iterable[Dict[str, Any]]) -> List[Point]:
    return [point_xy(point) for point in points or []]


def distance(a: Point, b: Point) -> float:
    return math.hypot(b["x"] - a["x"], b["y"] - a["y"])


def points_near(points: List[Point], center: Point, radius: float) -> List[Point]:
    return [point for point in points if distance(point, center) <= radius]


def bounds(points: Iterable[Point], margin: float = 0.0) -> Dict[str, float]:
    pts = [point for point in points if point and math.isfinite(point["x"]) and math.isfinite(point["y"])]
    xs = [point["x"] for point in pts]
    ys = [point["y"] for point in pts]
    min_x = min(xs) - margin
    max_x = max(xs) + margin
    min_y = min(ys) - margin
    max_y = max(ys) + margin
    return {
        "minX": min_x,
        "maxX": max_x,
        "minY": min_y,
        "maxY": max_y,
        "width": max_x - min_x,
        "height": max_y - min_y,
    }


def map_to_svg(point: Point, view: Dict[str, float], padding: float, scale: float) -> Tuple[float, float]:
    return padding + (point["x"] - view["minX"]) * scale, padding + (view["maxY"] - point["y"]) * scale


def path(points: List[Point], view: Dict[str, float], padding: float, scale: float, close: bool = False) -> str:
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


def marker(point: Point, view: Dict[str, float], padding: float, scale: float, fill: str, radius: float = 5.0) -> str:
    x, y = map_to_svg(point, view, padding, scale)
    return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{fill}" stroke="#050816" stroke-width="2"/>'


def canvas(view: Dict[str, float], width_limit: int = 1180, height_limit: int = 860) -> Tuple[float, float, int, int, List[str]]:
    padding = 36
    scale = min(
        (width_limit - padding * 2) / max(view["width"], 1.0),
        (height_limit - padding * 2) / max(view["height"], 1.0),
    )
    width = int(view["width"] * scale + padding * 2)
    height = int(view["height"] * scale + padding * 2)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Debug-only pit break decision view</title>",
        "<desc>Clean visualization for manual validation. No runtime or authoritative geometry changes.</desc>",
        '<rect width="100%" height="100%" fill="#050816"/>',
    ]
    return scale, padding, width, height, lines


def write_svg(output: Path, lines: List[str]) -> None:
    output.write_text("\n".join([*lines, "</svg>"]), encoding="utf-8")


def local_decision_svg(
    output: Path,
    main_center: List[Point],
    pit_center: List[Point],
    candidate: Dict[str, Any],
    pit_marker: Point,
    pit_marker_color: str,
) -> None:
    suspected_start = int(candidate["suspectedStartIndex"])
    suspected_end = int(candidate["suspectedEndIndex"])
    anchor_start = int(candidate["anchorStartIndex"])
    anchor_end = int(candidate["anchorEndIndex"])
    original_problem = main_center[suspected_start : suspected_end + 1]
    candidate_segment = points_xy(candidate["candidateSegment"])
    local_pit = points_near(pit_center, pit_marker, 140.0)
    view = bounds(
        [
            *original_problem,
            *candidate_segment,
            *local_pit,
            main_center[anchor_start],
            main_center[anchor_end],
            pit_marker,
        ],
        margin=28.0,
    )
    scale, padding, _, _, lines = canvas(view)
    lines.extend(
        [
            f'<path d="{path(main_center, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.10" opacity="0.42"/>',
            f'<path d="{path(pit_center, view, padding, scale)}" fill="none" stroke="#fde047" stroke-width="3.10" opacity="0.95"/>',
            f'<path d="{path(original_problem, view, padding, scale)}" fill="none" stroke="#ef4444" stroke-width="5.30" opacity="0.96"/>',
            f'<path d="{path(candidate_segment, view, padding, scale)}" fill="none" stroke="#22d3ee" stroke-width="4.20" opacity="0.98"/>',
            marker(pit_marker, view, padding, scale, pit_marker_color, radius=6.2),
            marker(main_center[anchor_start], view, padding, scale, "#f8fafc", radius=5.1),
            marker(main_center[anchor_end], view, padding, scale, "#f8fafc", radius=5.1),
        ]
    )
    write_svg(output, lines)


def overview_svg(
    output: Path,
    main_center: List[Point],
    pit_center: List[Point],
    entry_candidate: Dict[str, Any],
    exit_candidate: Dict[str, Any],
) -> None:
    entry_problem = main_center[int(entry_candidate["suspectedStartIndex"]) : int(entry_candidate["suspectedEndIndex"]) + 1]
    exit_problem = main_center[int(exit_candidate["suspectedStartIndex"]) : int(exit_candidate["suspectedEndIndex"]) + 1]
    entry_candidate_segment = points_xy(entry_candidate["candidateSegment"])
    exit_candidate_segment = points_xy(exit_candidate["candidateSegment"])
    view = bounds([*main_center, *pit_center], margin=70.0)
    scale, padding, _, _, lines = canvas(view, width_limit=1320, height_limit=920)
    lines.extend(
        [
            f'<path d="{path(main_center, view, padding, scale, close=True)}" fill="none" stroke="#94a3b8" stroke-width="1.15" opacity="0.62"/>',
            f'<path d="{path(pit_center, view, padding, scale)}" fill="none" stroke="#fde047" stroke-width="2.60" opacity="0.95"/>',
            f'<path d="{path(entry_problem, view, padding, scale)}" fill="none" stroke="#ef4444" stroke-width="4.60" opacity="0.96"/>',
            f'<path d="{path(exit_problem, view, padding, scale)}" fill="none" stroke="#ef4444" stroke-width="4.60" opacity="0.96"/>',
            f'<path d="{path(entry_candidate_segment, view, padding, scale)}" fill="none" stroke="#22d3ee" stroke-width="3.70" opacity="0.98"/>',
            f'<path d="{path(exit_candidate_segment, view, padding, scale)}" fill="none" stroke="#22d3ee" stroke-width="3.70" opacity="0.98"/>',
        ]
    )
    write_svg(output, lines)


def build() -> None:
    main = read_json(MAIN_TRACK_JSON)
    pitlane = read_json(PITLANE_MANUAL_JSON)
    entry_candidate = read_json(ENTRY_CANDIDATE_JSON)
    exit_candidate = read_json(EXIT_CANDIDATE_JSON)

    main_center = points_xy(main["centerline"])
    pit_center = points_xy(pitlane["pitCenterline"])

    local_decision_svg(
        ENTRY_CLEAN_SVG,
        main_center,
        pit_center,
        entry_candidate,
        PIT_MANUAL_START,
        "#22c55e",
    )
    local_decision_svg(
        EXIT_CLEAN_SVG,
        main_center,
        pit_center,
        exit_candidate,
        PIT_MANUAL_END,
        "#fb923c",
    )
    overview_svg(OVERVIEW_CLEAN_SVG, main_center, pit_center, entry_candidate, exit_candidate)

    print(ENTRY_CLEAN_SVG)
    print(EXIT_CLEAN_SVG)
    print(OVERVIEW_CLEAN_SVG)


if __name__ == "__main__":
    build()
