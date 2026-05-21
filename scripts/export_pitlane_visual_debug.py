"""Export debug-only Interlagos pitlane validation SVGs.

The geometry comes from previously generated JSON artifacts. This script does
not parse KN5, alter runtime state, or promote pitlane data into TrackGeometry.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.debug.pitlane_debug import build_pitlane_debug_payload  # noqa: E402


Point = Dict[str, float]


def _bounds(points: Iterable[Point], margin: float = 0.0) -> Dict[str, float]:
    pts = [point for point in points if point]
    xs = [point["x"] for point in pts]
    ys = [point["y"] for point in pts]
    min_x, max_x = min(xs) - margin, max(xs) + margin
    min_y, max_y = min(ys) - margin, max(ys) + margin
    return {
        "minX": min_x,
        "maxX": max_x,
        "minY": min_y,
        "maxY": max_y,
        "width": max(max_x - min_x, 1.0),
        "height": max(max_y - min_y, 1.0),
    }


def _merge_bounds(*bounds: Dict[str, float], margin: float = 0.0) -> Dict[str, float]:
    points = []
    for item in bounds:
        if not item:
            continue
        points.extend(
            [
                {"x": item["minX"], "y": item["minY"]},
                {"x": item["maxX"], "y": item["maxY"]},
            ]
        )
    return _bounds(points, margin=margin)


def _map_to_svg(point: Point, bounds: Dict[str, float], padding: float, scale: float) -> Tuple[float, float]:
    x = padding + (point["x"] - bounds["minX"]) * scale
    y = padding + (bounds["maxY"] - point["y"]) * scale
    return x, y


def _svg_context(bounds: Dict[str, float], max_width: int = 1200, max_height: int = 900, padding: int = 42):
    scale = min((max_width - padding * 2) / bounds["width"], (max_height - padding * 2) / bounds["height"])
    width = int(bounds["width"] * scale + padding * 2)
    height = int(bounds["height"] * scale + padding * 2)
    return width, height, scale, padding


def _path(points: List[Point], bounds: Dict[str, float], padding: float, scale: float, close: bool = False) -> str:
    if not points:
        return ""
    first_x, first_y = _map_to_svg(points[0], bounds, padding, scale)
    commands = [f"M {first_x:.2f} {first_y:.2f}"]
    for point in points[1:]:
        x, y = _map_to_svg(point, bounds, padding, scale)
        commands.append(f"L {x:.2f} {y:.2f}")
    if close:
        commands.append("Z")
    return " ".join(commands)


def _corridor_path(left: List[Point], right: List[Point], bounds: Dict[str, float], padding: float, scale: float) -> str:
    return _path([*left, *reversed(right)], bounds, padding, scale, close=True)


def _text(text: str, x: float, y: float, size: int = 12, color: str = "#e5e7eb", anchor: str = "start") -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" fill="{color}" font-size="{size}" '
        f'font-family="JetBrains Mono, Consolas, monospace" text-anchor="{anchor}">{html.escape(text)}</text>'
    )


def _marker(label: str, point: Optional[Point], bounds: Dict[str, float], padding: float, scale: float, color: str) -> str:
    if not point:
        return ""
    x, y = _map_to_svg(point, bounds, padding, scale)
    return "\n".join(
        [
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="{color}" stroke="#020617" stroke-width="2"/>',
            _text(label, x + 9, y - 9, size=11, color=color),
        ]
    )


def _direction_arrows(points: List[Point], bounds: Dict[str, float], padding: float, scale: float, color: str, count: int = 8) -> str:
    if len(points) < 3:
        return ""
    out = []
    step = max(1, len(points) // (count + 1))
    for index in range(step, len(points) - 1, step):
        a = points[index]
        b = points[min(index + 2, len(points) - 1)]
        ax, ay = _map_to_svg(a, bounds, padding, scale)
        bx, by = _map_to_svg(b, bounds, padding, scale)
        out.append(
            f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{bx:.2f}" y2="{by:.2f}" '
            f'stroke="{color}" stroke-width="2" marker-end="url(#arrow-{color[1:]})"/>'
        )
    return "\n".join(out)


def _draw_layers(payload: Dict[str, Any], bounds: Dict[str, float], padding: float, scale: float, zoom: bool = False) -> str:
    main = payload["mainTrack"]
    raw = payload["pitlaneRaw"]
    manual = payload["pitlaneTrimmedManual"]
    candidates = {candidate["name"]: candidate for candidate in payload["trimCandidates"]}
    candidate05 = candidates.get("candidate_05_05")
    candidate08 = candidates.get("candidate_08_08")

    layers = []
    main_fill = _corridor_path(main["leftEdge"], main["rightEdge"], bounds, padding, scale)
    if main_fill:
        layers.append(f'<path d="{main_fill}" fill="#475569" opacity="0.14" stroke="none"/>')
    main_center = _path(main["centerline"], bounds, padding, scale, close=True)
    if main_center:
        layers.append(f'<path d="{main_center}" fill="none" stroke="#64748b" stroke-width="{1.1 if zoom else 0.75}" opacity="0.5"/>')

    for loop in payload["pitlaneSurface"]["boundaryLoops"]:
        d = _path(loop.get("points", []), bounds, padding, scale, close=True)
        if d:
            layers.append(f'<path d="{d}" fill="#facc15" opacity="0.16" stroke="#facc15" stroke-width="1.4"/>')

    raw_corridor = _corridor_path(raw["leftEdge"], raw["rightEdge"], bounds, padding, scale)
    if raw_corridor:
        layers.append(f'<path d="{raw_corridor}" fill="#facc15" opacity="0.18" stroke="#fbbf24" stroke-width="1.0"/>')
    layers.append(
        f'<path d="{_path(raw["centerline"], bounds, padding, scale)}" fill="none" stroke="#fef3c7" '
        f'stroke-width="1.5" stroke-dasharray="8 7" opacity="0.92"/>'
    )

    if candidate05:
        layers.append(
            f'<path d="{_path(candidate05["centerline"], bounds, padding, scale)}" fill="none" '
            f'stroke="#22c55e" stroke-width="2.0" opacity="0.85"/>'
        )
    if candidate08:
        layers.append(
            f'<path d="{_path(candidate08["centerline"], bounds, padding, scale)}" fill="none" '
            f'stroke="#d946ef" stroke-width="1.8" opacity="0.82"/>'
        )

    manual_corridor = _corridor_path(manual["leftEdge"], manual["rightEdge"], bounds, padding, scale)
    if manual_corridor:
        layers.append(f'<path d="{manual_corridor}" fill="#f59e0b" opacity="0.26" stroke="#facc15" stroke-width="1.35"/>')
    layers.append(
        f'<path d="{_path(manual["centerline"], bounds, padding, scale)}" fill="none" '
        f'stroke="#fde047" stroke-width="3.0" opacity="0.95"/>'
    )
    layers.append(_direction_arrows(manual["centerline"], bounds, padding, scale, "#fde047", count=6 if zoom else 10))

    layers.append(_marker("raw start", raw["start"], bounds, padding, scale, "#fb923c"))
    layers.append(_marker("raw end", raw["end"], bounds, padding, scale, "#60a5fa"))
    layers.append(_marker("Pit Entry / manual 05_05 start", manual["start"], bounds, padding, scale, "#22d3ee"))
    layers.append(_marker("Pit Exit / manual 05_05 end", manual["end"], bounds, padding, scale, "#06b6d4"))

    if candidate05:
        layers.append(_marker("05_05", candidate05["start"], bounds, padding, scale, "#22c55e"))
        layers.append(_marker("05_05", candidate05["end"], bounds, padding, scale, "#22c55e"))
    if candidate08:
        layers.append(_marker("08_08", candidate08["start"], bounds, padding, scale, "#d946ef"))
        layers.append(_marker("08_08", candidate08["end"], bounds, padding, scale, "#d946ef"))

    return "\n".join(layer for layer in layers if layer)


def _legend(payload: Dict[str, Any], width: int) -> str:
    meta = payload["validationMetadata"]
    lines = [
        "MainTrackGeometry: gray",
        "PitLane raw: translucent yellow",
        "Manual 05_05: strong yellow",
        "candidate_05_05: green centerline",
        "candidate_08_08: magenta centerline",
        f"raw {meta['rawPointCount']} pts / {meta['rawLengthMeters']:.2f} m",
        f"manual {meta['trimmedPointCount']} pts / {meta['trimmedLengthMeters']:.2f} m",
        f"removed {meta['removedStartMeters']:.2f} m start, {meta['removedEndMeters']:.2f} m end",
        "runtimeChanged=false, aggressive trim rejected=true",
    ]
    x = width - 392
    out = [f'<rect x="{x}" y="18" width="374" height="174" fill="#020617" opacity="0.82" stroke="#334155"/>']
    for i, line in enumerate(lines):
        out.append(_text(line, x + 14, 40 + i * 18, size=11, color="#e2e8f0"))
    return "\n".join(out)


def _svg(title: str, payload: Dict[str, Any], bounds: Dict[str, float], output: Path, zoom: bool = False) -> None:
    width, height, scale, padding = _svg_context(bounds, max_width=1280, max_height=920, padding=46)
    layers = _draw_layers(payload, bounds, padding, scale, zoom=zoom)
    legend = _legend(payload, width) if not zoom else ""
    body = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs>
  <marker id="arrow-fde047" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
    <path d="M0,0 L0,6 L8,3 z" fill="#fde047"/>
  </marker>
</defs>
<rect width="100%" height="100%" fill="#050816"/>
{_text(title, 22, 28, size=16, color="#f8fafc")}
{_text("map-space projected consistently: screenX=padding+(x-minX)*scale, screenY=padding+(maxY-y)*scale", 22, height - 18, size=10, color="#94a3b8")}
{layers}
{legend}
</svg>
"""
    output.write_text(body, encoding="utf-8")


def export() -> Dict[str, str]:
    payload = build_pitlane_debug_payload(REPO_ROOT)
    debug_dir = REPO_ROOT / "data" / "debug"

    overview_bounds = _merge_bounds(payload["mainTrack"]["bounds"], payload["pitlaneSurface"]["bounds"], margin=24)
    manual = payload["pitlaneTrimmedManual"]
    raw = payload["pitlaneRaw"]
    candidates = {candidate["name"]: candidate for candidate in payload["trimCandidates"]}
    candidate05 = candidates.get("candidate_05_05", manual)
    candidate08 = candidates.get("candidate_08_08", manual)

    entry_points = [
        raw["start"],
        manual["start"],
        candidate05.get("start"),
        candidate08.get("start"),
        *raw["leftEdge"][:16],
        *raw["rightEdge"][:16],
    ]
    exit_points = [
        raw["end"],
        manual["end"],
        candidate05.get("end"),
        candidate08.get("end"),
        *raw["leftEdge"][-16:],
        *raw["rightEdge"][-16:],
    ]

    files = {
        "overview": debug_dir / "interlagos_pitlane_visual_debug_overview.svg",
        "entryZoom": debug_dir / "interlagos_pitlane_visual_debug_entry_zoom.svg",
        "exitZoom": debug_dir / "interlagos_pitlane_visual_debug_exit_zoom.svg",
    }
    _svg("Interlagos PitLane Visual Debug Overview", payload, overview_bounds, files["overview"])
    _svg("Interlagos PitLane Visual Debug Entry Zoom", payload, _bounds(entry_points, margin=34), files["entryZoom"], zoom=True)
    _svg("Interlagos PitLane Visual Debug Exit Zoom", payload, _bounds(exit_points, margin=34), files["exitZoom"], zoom=True)
    return {key: str(path) for key, path in files.items()}


if __name__ == "__main__":
    for key, value in export().items():
        print(f"{key}: {value}")
