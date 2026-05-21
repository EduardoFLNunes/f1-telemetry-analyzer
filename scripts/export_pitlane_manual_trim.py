from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"
CACHE_DIR = REPO_ROOT / "data" / "cache" / "tracks"


Point = Tuple[float, float]


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _xml(value: Any) -> str:
    return escape(str(value), quote=False)


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _bounds(points: Iterable[Sequence[float]]) -> Optional[Dict[str, float]]:
    values = [(float(point[0]), float(point[1])) for point in points]
    if not values:
        return None
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    return {
        "minX": min(xs),
        "maxX": max(xs),
        "minY": min(ys),
        "maxY": max(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
    }


def _merge_bounds(*bounds_items: Optional[Dict[str, float]]) -> Dict[str, float]:
    valid = [bounds for bounds in bounds_items if bounds]
    if not valid:
        return {"minX": -1.0, "maxX": 1.0, "minY": -1.0, "maxY": 1.0, "width": 2.0, "height": 2.0}
    min_x = min(float(bounds["minX"]) for bounds in valid)
    max_x = max(float(bounds["maxX"]) for bounds in valid)
    min_y = min(float(bounds["minY"]) for bounds in valid)
    max_y = max(float(bounds["maxY"]) for bounds in valid)
    return {"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y, "width": max_x - min_x, "height": max_y - min_y}


def _expand(bounds: Dict[str, float], pad: float) -> Dict[str, float]:
    return {
        "minX": bounds["minX"] - pad,
        "maxX": bounds["maxX"] + pad,
        "minY": bounds["minY"] - pad,
        "maxY": bounds["maxY"] + pad,
        "width": bounds["width"] + pad * 2,
        "height": bounds["height"] + pad * 2,
    }


def map_to_svg(point: Sequence[float], bounds: Dict[str, float], padding: float, scale: float) -> Point:
    return (
        padding + (float(point[0]) - float(bounds["minX"])) * scale,
        padding + (float(bounds["maxY"]) - float(point[1])) * scale,
    )


def _svg_mapper(bounds: Dict[str, float], *, width: int, height: int, padding: int = 36):
    scale = min((width - padding * 2) / max(1.0, bounds["width"]), (height - padding * 2) / max(1.0, bounds["height"]))

    def sx(point: Sequence[float]) -> Point:
        return map_to_svg(point, bounds, padding, scale)

    return sx


def _track_point(point: Dict[str, Any]) -> Point:
    return float(point["x"]), float(point.get("y", point.get("z", 0.0)))


def _xy_points(items: Sequence[Dict[str, Any]]) -> List[Point]:
    return [(float(point["x"]), float(point["y"])) for point in items]


def _polyline(points: Sequence[Sequence[float]], sx, *, stroke: str, width: float, opacity: float = 1.0, dash: Optional[str] = None) -> str:
    if not points:
        return ""
    text = " ".join(f"{x:.2f},{y:.2f}" for x, y in (sx(point) for point in points))
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{text}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-opacity="{opacity}" stroke-linejoin="round" stroke-linecap="round"{dash_attr}/>'


def _polygon(points: Sequence[Sequence[float]], sx, *, fill: str, opacity: float, stroke: str = "none", width: float = 1.0) -> str:
    if not points:
        return ""
    text = " ".join(f"{x:.2f},{y:.2f}" for x, y in (sx(point) for point in points))
    return f'<polygon points="{text}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{width}"/>'


def _candidate(minimal: Dict[str, Any], name: str) -> Dict[str, Any]:
    for item in minimal.get("candidates", []):
        if item.get("name") == name:
            return item
    raise KeyError(name)


def _draw_main(parts: List[str], main: Dict[str, Any], sx) -> None:
    left = [_track_point(point) for point in main.get("boundsLeft", [])]
    right = [_track_point(point) for point in main.get("boundsRight", [])]
    if left and right:
        parts.append(_polygon(left + list(reversed(right)), sx, fill="#8b95a7", opacity=0.12, stroke="#8b95a7", width=0.5))


def _label(parts: List[str], sx, point: Sequence[float], label: str, color: str, *, dy: float = -8.0) -> None:
    x, y = sx(point)
    parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{color}"/>')
    parts.append(f'<text x="{x + 7:.2f}" y="{y + dy:.2f}" fill="{color}" font-size="10" font-family="monospace">{_xml(label)}</text>')


def _draw_geometry(parts: List[str], sx, raw: Dict[str, Any], manual: Dict[str, Any], candidate08: Dict[str, Any]) -> None:
    raw_left = _xy_points(raw["pitLeftEdge"])
    raw_right = _xy_points(raw["pitRightEdge"])
    raw_center = _xy_points(raw["pitCenterline"])
    manual_center = _xy_points(manual["pitCenterline"])
    c08_center = _xy_points(candidate08["pitCenterline"])
    if raw_left and raw_right:
        parts.append(_polygon(raw_left + list(reversed(raw_right)), sx, fill="#eab308", opacity=0.24, stroke="#facc15", width=1.0))
    parts.append(_polyline(raw_center, sx, stroke="#facc15", width=2.2, opacity=0.45, dash="7,5"))
    parts.append(_polyline(manual_center, sx, stroke="#22c55e", width=4.0, opacity=0.98))
    parts.append(_polyline(c08_center, sx, stroke="#d946ef", width=2.6, opacity=0.95, dash="9,5"))
    _label(parts, sx, raw_center[0], "raw start", "#facc15", dy=14)
    _label(parts, sx, raw_center[-1], "raw end", "#facc15", dy=-10)
    _label(parts, sx, manual_center[0], "manual_05_05 start", "#22c55e", dy=20)
    _label(parts, sx, manual_center[-1], "manual_05_05 end", "#22c55e", dy=-14)
    _label(parts, sx, c08_center[0], "candidate_08_08 start", "#d946ef", dy=34)
    _label(parts, sx, c08_center[-1], "candidate_08_08 end", "#d946ef", dy=-28)


def _write_svg(path: Path, *, main: Dict[str, Any], raw: Dict[str, Any], manual: Dict[str, Any], candidate08: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    width, height = 1400, 1000
    points = []
    points.extend(_xy_points(raw["pitLeftEdge"]))
    points.extend(_xy_points(raw["pitRightEdge"]))
    points.extend(_xy_points(raw["pitCenterline"]))
    points.extend(_xy_points(manual["pitCenterline"]))
    points.extend(_xy_points(candidate08["pitCenterline"]))
    main_bounds = main.get("bounds")
    bounds = _expand(_merge_bounds(main_bounds, _bounds(points)), 20.0)
    sx = _svg_mapper(bounds, width=width, height=height)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#080b10"/>',
        '<text x="18" y="28" fill="#e2e8f0" font-size="16" font-family="monospace">PitLaneGeometryTrimmedManual candidate_05_05</text>',
        '<text x="18" y="50" fill="#94a3b8" font-size="11" font-family="monospace">debug/export only; runtime unchanged; aggressive automatic trim rejected</text>',
    ]
    _draw_main(parts, main, sx)
    _draw_geometry(parts, sx, raw, manual, candidate08)
    legend = [
        ("MainTrackGeometry", "#8b95a7"),
        ("raw surface corridor", "#facc15"),
        ("manual_05_05", "#22c55e"),
        ("candidate_08_08", "#d946ef"),
    ]
    for index, (label, color) in enumerate(legend):
        yy = 82 + index * 18
        parts.append(f'<rect x="18" y="{yy - 10}" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="34" y="{yy}" fill="#cbd5e1" font-size="11" font-family="monospace">{_xml(label)}</text>')
    parts.append(f'<rect x="18" y="170" width="430" height="88" fill="#020617" fill-opacity="0.75" stroke="#1e293b"/>')
    text_rows = [
        f'manualTrimSelected={metrics["manualTrimSelected"]}',
        f'05_05 removes start/end={metrics["removedStartMeters"]:.2f}m/{metrics["removedEndMeters"]:.2f}m',
        f'08_08 removes start/end={candidate08["removedStartMeters"]:.2f}m/{candidate08["removedEndMeters"]:.2f}m',
        f'rawLength={metrics["rawLengthMeters"]:.2f}m manualLength={metrics["lengthMeters"]:.2f}m',
    ]
    for index, row in enumerate(text_rows):
        parts.append(f'<text x="30" y="{190 + index * 16}" fill="#cbd5e1" font-size="11" font-family="monospace">{_xml(row)}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    raw = _load_json(DEBUG_DIR / "interlagos_pitlane_surface_derived_geometry.json")
    minimal = _load_json(DEBUG_DIR / "interlagos_pitlane_trim_candidates_minimal.json")
    main = _load_json(CACHE_DIR / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json")
    manual = _candidate(minimal, "candidate_05_05")
    candidate08 = _candidate(minimal, "candidate_08_08")
    generated_at = datetime.now(timezone.utc).isoformat()
    metrics = {
        "generatedAt": generated_at,
        "runtimeChanged": False,
        "mainTrackGeometryChanged": False,
        "trackPhysicsGeometryChanged": False,
        "canonicalMapSpaceChanged": False,
        "pitLaneAiUsedForGeometry": False,
        "manualTrimSelected": "candidate_05_05",
        "manualTrimReason": "minimal trim; aggressive automatic trim was rejected",
        "aggressiveTrimRejected": True,
        "rawPointCount": raw.get("metadata", {}).get("pointCount") or len(raw["pitCenterline"]),
        "pointCount": manual["pointCount"],
        "rawLengthMeters": minimal["rawLength"],
        "lengthMeters": manual["length"],
        "startTrimPoints": manual["startTrimPoints"],
        "endTrimPoints": manual["endTrimPoints"],
        "removedStartMeters": manual["removedStartMeters"],
        "removedEndMeters": manual["removedEndMeters"],
        "startCoordinate": manual["startCoordinate"],
        "endCoordinate": manual["endCoordinate"],
        "comparisonCandidate": {
            "name": "candidate_08_08",
            "pointCount": candidate08["pointCount"],
            "lengthMeters": candidate08["length"],
            "removedStartMeters": candidate08["removedStartMeters"],
            "removedEndMeters": candidate08["removedEndMeters"],
            "startCoordinate": candidate08["startCoordinate"],
            "endCoordinate": candidate08["endCoordinate"],
        },
        "diagnostics": [
            {
                "code": "manual_debug_export_only",
                "message": "Manual 05_05 trim is exported for validation and is not connected to runtime.",
            }
        ],
    }
    payload = {
        **metrics,
        "source": "PitLaneGeometryRaw",
        "projection": raw.get("projection"),
        "pitLeftEdge": manual["pitLeftEdge"],
        "pitCenterline": manual["pitCenterline"],
        "pitRightEdge": manual["pitRightEdge"],
        "widthStats": manual["widthStats"],
        "metadata": {
            "manualTrimSelected": metrics["manualTrimSelected"],
            "manualTrimReason": metrics["manualTrimReason"],
            "aggressiveTrimRejected": True,
            "runtimeChanged": False,
        },
    }
    json_path = DEBUG_DIR / "interlagos_pitlane_trimmed_manual_05_05.json"
    svg_path = DEBUG_DIR / "interlagos_pitlane_trimmed_manual_05_05.svg"
    compare_svg_path = DEBUG_DIR / "interlagos_pitlane_raw_vs_manual_05_05_vs_08_08.svg"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_svg(svg_path, main=main, raw=raw, manual=manual, candidate08=candidate08, metrics=metrics)
    _write_svg(compare_svg_path, main=main, raw=raw, manual=manual, candidate08=candidate08, metrics=metrics)
    print(json.dumps({"json": str(json_path), "svg": str(svg_path), "comparisonSvg": str(compare_svg_path), **metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
