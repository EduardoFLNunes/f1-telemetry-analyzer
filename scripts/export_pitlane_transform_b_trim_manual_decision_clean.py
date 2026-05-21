"""Clean manual-decision SVG for PitLane transform B trims.

This is debug/export only. It compares candidate_00_00, candidate_05_05, and
candidate_08_08 without selecting or promoting any trim.
"""
from __future__ import annotations

import html
import json
import math
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"
CACHE_DIR = REPO_ROOT / "data" / "cache" / "tracks"

MAIN_TRACK_JSON = CACHE_DIR / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
AI_VALIDATION_JSON = DEBUG_DIR / "ai_parser_validation.json"
TRIM_B_JSON = DEBUG_DIR / "interlagos_pitlane_trim_candidates_minimal_transform_b.json"
OLD_DERIVED_A_JSON = DEBUG_DIR / "interlagos_pitlane_surface_derived_geometry.json"

OUTPUT_JSON = DEBUG_DIR / "interlagos_pitlane_transform_b_trim_manual_decision_clean.json"
OUTPUT_SVG = DEBUG_DIR / "interlagos_pitlane_transform_b_trim_manual_decision_clean.svg"

Point = Tuple[float, float]


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def round_value(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def point_xy(point: Any) -> Point:
    if isinstance(point, dict):
        return (float(point["x"]), float(point.get("y", point.get("z", 0.0))))
    return (float(point[0]), float(point[1]))


def points_xy(points: Iterable[Any]) -> List[Point]:
    return [point_xy(point) for point in points or []]


def point_payload(point: Point) -> Dict[str, float]:
    return {"x": round_value(point[0]), "y": round_value(point[1])}


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def polyline_length(points: Sequence[Point]) -> float:
    return sum(distance(points[index - 1], points[index]) for index in range(1, len(points)))


def bounds(points: Iterable[Point], pad: float = 0.0) -> Dict[str, float]:
    values = [point for point in points if math.isfinite(point[0]) and math.isfinite(point[1])]
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    return {
        "minX": min(xs) - pad,
        "maxX": max(xs) + pad,
        "minY": min(ys) - pad,
        "maxY": max(ys) + pad,
        "width": max(xs) - min(xs) + pad * 2,
        "height": max(ys) - min(ys) + pad * 2,
    }


def expand_bounds(base: Dict[str, float], pad: float) -> Dict[str, float]:
    return {
        "minX": base["minX"] - pad,
        "maxX": base["maxX"] + pad,
        "minY": base["minY"] - pad,
        "maxY": base["maxY"] + pad,
        "width": base["width"] + pad * 2,
        "height": base["height"] + pad * 2,
    }


def parse_ai_block20(path: str) -> List[Point]:
    ai_path = Path(path)
    data = ai_path.read_bytes()
    _version, declared_count = struct.unpack_from("<II", data, 0)
    available = max(0, (len(data) - 16) // 20)
    count = min(int(declared_count), available)
    points: List[Point] = []
    for index in range(count):
        x, _world_y, z, _distance, _raw_index = struct.unpack_from("<3f f I", data, 16 + index * 20)
        points.append((float(x), float(z)))
    return points


def candidate_by_name(data: Dict[str, Any], name: str) -> Dict[str, Any]:
    for candidate in data.get("candidates", []):
        if candidate.get("name") == name:
            return candidate
    raise KeyError(name)


def candidate_center(candidate: Dict[str, Any]) -> List[Point]:
    return points_xy(candidate.get("pitCenterline", []))


def map_to_panel(point: Point, view: Dict[str, float], rect: Tuple[float, float, float, float], inner_pad: float = 28.0) -> Point:
    x, y, width, height = rect
    usable_w = max(1.0, width - inner_pad * 2)
    usable_h = max(1.0, height - inner_pad * 2)
    scale = min(usable_w / max(view["width"], 1e-9), usable_h / max(view["height"], 1e-9))
    sx = x + inner_pad + (point[0] - view["minX"]) * scale
    sy = y + inner_pad + (view["maxY"] - point[1]) * scale
    return sx, sy


def svg_path(points: Sequence[Point], view: Dict[str, float], rect: Tuple[float, float, float, float], *, close: bool = False) -> str:
    if not points:
        return ""
    x, y = map_to_panel(points[0], view, rect)
    parts = [f"M {x:.2f} {y:.2f}"]
    for point in points[1:]:
        x, y = map_to_panel(point, view, rect)
        parts.append(f"L {x:.2f} {y:.2f}")
    if close:
        parts.append("Z")
    return " ".join(parts)


def label(
    text: str,
    point: Point,
    view: Dict[str, float],
    rect: Tuple[float, float, float, float],
    color: str,
    *,
    dx: float = 8.0,
    dy: float = -7.0,
    radius: float = 4.2,
) -> str:
    x, y = map_to_panel(point, view, rect)
    safe = html.escape(text)
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{color}" stroke="#050816" stroke-width="1.4"/>'
        f'<text x="{x + dx:.2f}" y="{y + dy:.2f}" fill="{color}" font-size="10.5" font-family="Consolas, monospace" '
        f'paint-order="stroke" stroke="#050816" stroke-width="3" stroke-linejoin="round">{safe}</text>'
    )


def draw_polyline(
    parts: List[str],
    points: Sequence[Point],
    view: Dict[str, float],
    rect: Tuple[float, float, float, float],
    *,
    color: str,
    width: float,
    opacity: float = 1.0,
    dash: Optional[str] = None,
    close: bool = False,
) -> None:
    if not points:
        return
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    parts.append(
        f'<path d="{svg_path(points, view, rect, close=close)}" fill="none" stroke="{color}" '
        f'stroke-width="{width:.2f}" opacity="{opacity:.3f}" stroke-linecap="round" stroke-linejoin="round"{dash_attr}/>'
    )


def panel_title(parts: List[str], rect: Tuple[float, float, float, float], title: str, subtitle: str) -> None:
    x, y, width, height = rect
    parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" fill="#07111f" stroke="#1e293b" stroke-width="1"/>')
    parts.append(f'<text x="{x + 14:.1f}" y="{y + 23:.1f}" fill="#e2e8f0" font-size="13" font-family="Consolas, monospace">{html.escape(title)}</text>')
    parts.append(f'<text x="{x + 14:.1f}" y="{y + 40:.1f}" fill="#94a3b8" font-size="10" font-family="Consolas, monospace">{html.escape(subtitle)}</text>')


def draw_layers(
    parts: List[str],
    rect: Tuple[float, float, float, float],
    view: Dict[str, float],
    main_track: Sequence[Point],
    fast_lane: Sequence[Point],
    old_a: Sequence[Point],
    centers: Dict[str, List[Point]],
    *,
    clip_id: str,
    show_full_labels: bool,
    start_zoom: bool = False,
    end_zoom: bool = False,
) -> None:
    colors = {
        "candidate_00_00": "#facc15",
        "candidate_05_05": "#22c55e",
        "candidate_08_08": "#d946ef",
    }
    parts.append(f'<g clip-path="url(#{clip_id})">')
    draw_polyline(parts, main_track, view, rect, color="#94a3b8", width=1.05, opacity=0.58, close=True)
    draw_polyline(parts, fast_lane, view, rect, color="#a855f7", width=0.95, opacity=0.62, dash="7 6", close=True)
    draw_polyline(parts, old_a, view, rect, color="#ef4444", width=1.25, opacity=0.18)
    draw_polyline(parts, centers["candidate_00_00"], view, rect, color=colors["candidate_00_00"], width=4.2, opacity=0.36)
    draw_polyline(parts, centers["candidate_05_05"], view, rect, color=colors["candidate_05_05"], width=3.9, opacity=0.98)
    draw_polyline(parts, centers["candidate_08_08"], view, rect, color=colors["candidate_08_08"], width=3.3, opacity=0.96)
    parts.append("</g>")

    if not show_full_labels:
        return

    label_specs = [
        ("candidate_00_00", "00_00", -20.0, "#facc15"),
        ("candidate_05_05", "05_05", 0.0, "#22c55e"),
        ("candidate_08_08", "08_08", 20.0, "#d946ef"),
    ]
    for name, short_name, y_offset, color in label_specs:
        center = centers[name]
        if start_zoom:
            parts.append(label(f"{short_name} start", center[0], view, rect, color, dy=-9.0 + y_offset))
        if end_zoom:
            parts.append(label(f"{short_name} end", center[-1], view, rect, color, dy=-9.0 + y_offset))


def draw_endpoint_labels(
    parts: List[str],
    rect: Tuple[float, float, float, float],
    view: Dict[str, float],
    candidates: Dict[str, Dict[str, Any]],
    centers: Dict[str, List[Point]],
    *,
    endpoint: str,
) -> None:
    color_by_name = {
        "candidate_00_00": "#facc15",
        "candidate_05_05": "#22c55e",
        "candidate_08_08": "#d946ef",
    }
    vertical_offsets = {
        "candidate_00_00": -22.0,
        "candidate_05_05": 0.0,
        "candidate_08_08": 22.0,
    }
    short = {
        "candidate_00_00": "00_00",
        "candidate_05_05": "05_05",
        "candidate_08_08": "08_08",
    }
    for name in ("candidate_00_00", "candidate_05_05", "candidate_08_08"):
        candidate = candidates[name]
        center = centers[name]
        point = center[0] if endpoint == "start" else center[-1]
        removed = candidate["removedStartMeters"] if endpoint == "start" else candidate["removedEndMeters"]
        parts.append(
            label(
                f"{short[name]} {endpoint} remove {removed:.2f}m",
                point,
                view,
                rect,
                color_by_name[name],
                dy=vertical_offsets[name],
            )
        )


def build_payload(candidates: Dict[str, Dict[str, Any]], centers: Dict[str, List[Point]]) -> Dict[str, Any]:
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "trackName": "vhe_interlagos",
        "trackConfig": "gp",
        "source": "debug_transform_b_trim_manual_decision_clean",
        "debugOnly": True,
        "selectedTransform": "B",
        "transformUsed": "mapX = worldX, mapY = worldZ",
        "oldTransformInvalidated": True,
        "candidatesCompared": ["candidate_00_00", "candidate_05_05", "candidate_08_08"],
        "recommendedManualTrimCandidate": None,
        "selectedAutomatically": False,
        "runtimeChanged": False,
        "geometryChanged": False,
        "authoritativeGeometryChanged": False,
        "mainTrackGeometryChanged": False,
        "trackPhysicsGeometryChanged": False,
        "pitLaneGeometryChanged": False,
        "projectionChanged": False,
        "mapSpaceChanged": False,
        "readyForRuntimeIntegration": False,
        "entryExitTransitionsChanged": False,
        "candidates": [
            {
                "name": name,
                "pointCount": len(centers[name]),
                "lengthMeters": round_value(polyline_length(centers[name])),
                "removedStartMeters": candidates[name]["removedStartMeters"],
                "removedEndMeters": candidates[name]["removedEndMeters"],
                "startCoordinate": point_payload(centers[name][0]),
                "endCoordinate": point_payload(centers[name][-1]),
            }
            for name in ("candidate_00_00", "candidate_05_05", "candidate_08_08")
        ],
        "visualLayers": {
            "mainTrackGeometry": "gray",
            "fastLaneAi": "purple dashed",
            "pitLaneBRawCandidate0000": "yellow translucent",
            "candidate0505": "green",
            "candidate0808": "magenta",
            "oldTransformA": "red weak comparison only",
        },
        "exports": {"json": str(OUTPUT_JSON), "svg": str(OUTPUT_SVG)},
    }


def write_svg(
    main_track: Sequence[Point],
    fast_lane: Sequence[Point],
    old_a: Sequence[Point],
    candidates: Dict[str, Dict[str, Any]],
    centers: Dict[str, List[Point]],
) -> None:
    width = 1680
    height = 1320
    overview_rect = (34.0, 72.0, 1612.0, 650.0)
    start_rect = (34.0, 750.0, 790.0, 530.0)
    end_rect = (856.0, 750.0, 790.0, 530.0)

    overview_view = bounds([*main_track, *fast_lane, *old_a, *centers["candidate_00_00"]], pad=70.0)
    start_points: List[Point] = []
    end_points: List[Point] = []
    for center in centers.values():
        start_points.extend(center[:32])
        end_points.extend(center[-32:])
    start_view = expand_bounds(bounds(start_points), 34.0)
    end_view = expand_bounds(bounds(end_points), 34.0)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Interlagos PitLane transform B trim manual decision clean</title>",
        '<rect width="100%" height="100%" fill="#050816"/>',
        "<defs>",
        f'<clipPath id="overview-clip"><rect x="{overview_rect[0]:.1f}" y="{overview_rect[1]:.1f}" width="{overview_rect[2]:.1f}" height="{overview_rect[3]:.1f}"/></clipPath>',
        f'<clipPath id="start-clip"><rect x="{start_rect[0]:.1f}" y="{start_rect[1]:.1f}" width="{start_rect[2]:.1f}" height="{start_rect[3]:.1f}"/></clipPath>',
        f'<clipPath id="end-clip"><rect x="{end_rect[0]:.1f}" y="{end_rect[1]:.1f}" width="{end_rect[2]:.1f}" height="{end_rect[3]:.1f}"/></clipPath>',
        "</defs>",
        '<text x="34" y="34" fill="#e2e8f0" font-size="17" font-family="Consolas, monospace">PitLane Transform B Trim Manual Decision</text>',
        '<text x="34" y="56" fill="#94a3b8" font-size="11" font-family="Consolas, monospace">debug/export only; no automatic selection; old Transform A is weak red comparison only</text>',
    ]

    panel_title(parts, overview_rect, "1. Overview completo", "MainTrack, fast_lane.ai, raw B 00_00, 05_05, 08_08")
    draw_layers(parts, overview_rect, overview_view, main_track, fast_lane, old_a, centers, clip_id="overview-clip", show_full_labels=False)
    parts.append(label("00_00 raw B", centers["candidate_00_00"][len(centers["candidate_00_00"]) // 2], overview_view, overview_rect, "#facc15", dy=-22))
    parts.append(label("05_05", centers["candidate_05_05"][len(centers["candidate_05_05"]) // 2 - 10], overview_view, overview_rect, "#22c55e"))
    parts.append(label("08_08", centers["candidate_08_08"][len(centers["candidate_08_08"]) // 2 + 10], overview_view, overview_rect, "#d946ef", dy=16))
    parts.append(label("old Transform A", old_a[len(old_a) // 2], overview_view, overview_rect, "#ef4444", dy=-18))

    panel_title(parts, start_rect, "2. Zoom start da pitlane B", "labels mostram metros removidos no inicio")
    draw_layers(parts, start_rect, start_view, main_track, fast_lane, old_a, centers, clip_id="start-clip", show_full_labels=False)
    draw_endpoint_labels(parts, start_rect, start_view, candidates, centers, endpoint="start")

    panel_title(parts, end_rect, "3. Zoom end da pitlane B", "labels mostram metros removidos no fim")
    draw_layers(parts, end_rect, end_view, main_track, fast_lane, old_a, centers, clip_id="end-clip", show_full_labels=False)
    draw_endpoint_labels(parts, end_rect, end_view, candidates, centers, endpoint="end")

    legend_items = [
        ("MainTrackGeometry", "#94a3b8"),
        ("fast_lane.ai", "#a855f7"),
        ("PitLane B raw 00_00", "#facc15"),
        ("candidate_05_05", "#22c55e"),
        ("candidate_08_08", "#d946ef"),
        ("old Transform A invalid", "#ef4444"),
    ]
    legend_x = 1272
    legend_y = 94
    parts.append(f'<rect x="{legend_x - 12}" y="{legend_y - 22}" width="350" height="136" rx="6" fill="#020617" fill-opacity="0.72" stroke="#1e293b"/>')
    for index, (text, color) in enumerate(legend_items):
        y = legend_y + index * 19
        dash = ' stroke-dasharray="7 5"' if "fast_lane" in text else ""
        opacity = "0.18" if "old" in text else "0.95"
        parts.append(f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 30}" y2="{y}" stroke="{color}" stroke-width="4" opacity="{opacity}"{dash}/>')
        parts.append(f'<text x="{legend_x + 42}" y="{y + 4}" fill="#cbd5e1" font-size="10.5" font-family="Consolas, monospace">{html.escape(text)}</text>')

    parts.append("</svg>")
    OUTPUT_SVG.write_text("\n".join(parts), encoding="utf-8")


def build() -> None:
    main_data = read_json(MAIN_TRACK_JSON)
    ai_data = read_json(AI_VALIDATION_JSON)
    trim_b = read_json(TRIM_B_JSON)
    old_a_data = read_json(OLD_DERIVED_A_JSON)

    main_track = points_xy(main_data.get("centerline", []))
    fast_lane = parse_ai_block20(ai_data["manifest"]["fastLaneAi"])
    old_a = points_xy(old_a_data.get("pitCenterline", []))
    candidates = {
        name: candidate_by_name(trim_b, name)
        for name in ("candidate_00_00", "candidate_05_05", "candidate_08_08")
    }
    centers = {name: candidate_center(candidate) for name, candidate in candidates.items()}

    payload = build_payload(candidates, centers)
    write_json = json.dumps(payload, indent=2)
    OUTPUT_JSON.write_text(write_json, encoding="utf-8")
    write_svg(main_track, fast_lane, old_a, candidates, centers)
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_SVG}")
    for candidate in payload["candidates"]:
        print(
            f"{candidate['name']}: length={candidate['lengthMeters']:.3f}m "
            f"removed={candidate['removedStartMeters']:.2f}/{candidate['removedEndMeters']:.2f}m"
        )


if __name__ == "__main__":
    build()
