"""Debug-only PitArea exit validation helpers.

The functions here classify already-rendered map-space car positions against
PitAreaGeometry. They never modify projection, TrackPhysicsGeometry, or the
authoritative MainTrackGeometry.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


Point = Tuple[float, float]

MAIN_TRACK_CACHE = "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
PIT_AREA_SURFACE_JSON = "interlagos_pit_area_surface.json"
PIT_AREA_COMPONENTS_JSON = "interlagos_pit_area_components.json"
PIT_AREA_CENTERLINES_JSON = "interlagos_pit_area_centerlines.json"

EXIT_LIVE_VALIDATION_JSON = "interlagos_pit_area_exit_access_live_validation.json"
EXIT_LIVE_VALIDATION_SVG = "interlagos_pit_area_exit_access_live_validation.svg"
RECORDED_CAR_PATH_JSON = "interlagos_pit_area_recorded_car_path.json"
RECORDED_CAR_PATH_SVG = "interlagos_pit_area_recorded_car_path.svg"
EXIT_VALIDATION_REPORT_JSON = "interlagos_pit_area_exit_access_validation_report.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _point(raw: Any, *, flip_y: bool = False) -> Optional[Point]:
    if isinstance(raw, dict):
        x = raw.get("x")
        y = raw.get("y", raw.get("z"))
    elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
        x, y = raw[0], raw[1]
    else:
        return None
    try:
        result = (float(x), float(y))
    except (TypeError, ValueError):
        return None
    return (result[0], -result[1]) if flip_y else result


def _points(raw_points: Iterable[Any], *, flip_y: bool = False) -> List[Point]:
    return [point for point in (_point(raw, flip_y=flip_y) for raw in raw_points or []) if point is not None]


def _point_payload(point: Point) -> Dict[str, float]:
    return {"x": round(float(point[0]), 6), "y": round(float(point[1]), 6)}


def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _nearest_point_on_segment(point: Point, a: Point, b: Point) -> Tuple[Point, float]:
    ab = (b[0] - a[0], b[1] - a[1])
    denom = ab[0] * ab[0] + ab[1] * ab[1]
    if denom <= 1e-12:
        return a, _distance(point, a)
    ap = (point[0] - a[0], point[1] - a[1])
    t = max(0.0, min(1.0, (ap[0] * ab[0] + ap[1] * ab[1]) / denom))
    projected = (a[0] + ab[0] * t, a[1] + ab[1] * t)
    return projected, _distance(point, projected)


def _distance_to_polyline(point: Point, line: Sequence[Point]) -> float:
    if len(line) < 2:
        return float("inf")
    return min(_nearest_point_on_segment(point, line[index - 1], line[index])[1] for index in range(1, len(line)))


def _point_in_triangle(point: Point, vertices: Sequence[Point]) -> bool:
    if len(vertices) < 3:
        return False
    a, b, c = vertices[:3]
    denom = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(denom) <= 1e-12:
        return False
    u = ((b[1] - c[1]) * (point[0] - c[0]) + (c[0] - b[0]) * (point[1] - c[1])) / denom
    v = ((c[1] - a[1]) * (point[0] - c[0]) + (a[0] - c[0]) * (point[1] - c[1])) / denom
    w = 1.0 - u - v
    return u >= -1e-6 and v >= -1e-6 and w >= -1e-6


def _triangle_points(triangle: Dict[str, Any]) -> List[Point]:
    return _points(triangle.get("vertices", []))


def _decimate(items: Sequence[Any], max_count: int) -> List[Any]:
    if len(items) <= max_count:
        return list(items)
    step = max(1, math.ceil(len(items) / max_count))
    return [item for index, item in enumerate(items) if index % step == 0][:max_count]


def _component(components: Dict[str, Any], name: str) -> Dict[str, Any]:
    for item in components.get("components", []) or []:
        if item.get("name") == name:
            return item
    return {}


def _component_triangles(components: Dict[str, Any], name: str, max_count: int) -> List[List[Point]]:
    return [
        _triangle_points(triangle)
        for triangle in _decimate(_component(components, name).get("sampleTriangles", []) or [], max_count)
    ]


class PitAreaDebugClassifier:
    def __init__(self, scene: Dict[str, Any]):
        centerlines = scene["centerlines"]
        components = scene["components"]
        self.main_track = _decimate(scene["mainTrack"], 700)
        self.entry_line = _points((centerlines.get("PitEntryAccessCenterline") or {}).get("centerline", []))
        self.corridor_line = _points((centerlines.get("PitLaneCorridorCenterline") or {}).get("centerline", []))
        self.exit_line = _points((centerlines.get("PitExitAccessCenterline") or {}).get("centerline", []))
        self.entry_triangles = _component_triangles(components, "PitEntryAccessArea", 300)
        self.corridor_triangles = _component_triangles(components, "PitLaneCorridor", 420)
        self.exit_triangles = _component_triangles(components, "PitExitAccessArea", 360)
        self.other_triangles = _component_triangles(components, "OtherPitArea", 260)

    def _inside_any(self, point: Point, triangles: Sequence[Sequence[Point]]) -> bool:
        return any(_point_in_triangle(point, triangle) for triangle in triangles)

    def classify(self, point: Point) -> Dict[str, Any]:
        distance_to_entry = _distance_to_polyline(point, self.entry_line)
        distance_to_corridor = _distance_to_polyline(point, self.corridor_line)
        distance_to_exit = _distance_to_polyline(point, self.exit_line)
        distance_to_main = _distance_to_polyline(point, self.main_track)
        if distance_to_entry <= 7.0:
            area, confidence = "pit_entry_access", "high"
        elif distance_to_exit <= 7.0:
            area, confidence = "pit_exit_access", "high"
        elif distance_to_corridor <= 7.5:
            area, confidence = "pit_corridor", "high"
        elif self._inside_any(point, self.exit_triangles):
            area, confidence = "pit_exit_access", "high"
        elif self._inside_any(point, self.entry_triangles):
            area, confidence = "pit_entry_access", "high"
        elif self._inside_any(point, self.corridor_triangles):
            area, confidence = "pit_corridor", "high"
        elif self._inside_any(point, self.other_triangles):
            area, confidence = "pit_area_other", "medium"
        elif distance_to_exit <= 11.0:
            area, confidence = "pit_exit_access", "medium"
        elif distance_to_corridor <= 12.0:
            area, confidence = "pit_corridor", "medium"
        elif distance_to_main <= 12.0:
            area, confidence = "main_track", "medium"
        else:
            area, confidence = "unknown", "low"
        return {
            "areaClassification": area,
            "distanceToEntryAccess": _round(distance_to_entry),
            "distanceToExitAccess": _round(distance_to_exit),
            "distanceToPitCorridor": _round(distance_to_corridor),
            "distanceToMainTrack": _round(distance_to_main),
            "confidence": confidence,
        }


def _round(value: float) -> Optional[float]:
    return round(float(value), 6) if math.isfinite(value) else None


def _load_scene(repo_root: Path) -> Dict[str, Any]:
    debug_dir = repo_root / "data" / "debug"
    cache_dir = repo_root / "data" / "cache" / "tracks"
    main = _read_json(cache_dir / MAIN_TRACK_CACHE)
    centerlines = _read_json(debug_dir / PIT_AREA_CENTERLINES_JSON).get("centerlines", {})
    ai_references = _read_json(debug_dir / PIT_AREA_CENTERLINES_JSON).get("aiReferences", {})
    return {
        "mainTrack": _points(main.get("centerline", []), flip_y=True),
        "surface": _read_json(debug_dir / PIT_AREA_SURFACE_JSON),
        "components": _read_json(debug_dir / PIT_AREA_COMPONENTS_JSON),
        "centerlines": centerlines,
        "fastLane": _points((ai_references.get("fastLane") or {}).get("centerline", [])),
        "pitLaneAi": _points((ai_references.get("pitLane") or {}).get("centerline", [])),
        "entry": _points((centerlines.get("PitEntryAccessCenterline") or {}).get("centerline", [])),
        "corridor": _points((centerlines.get("PitLaneCorridorCenterline") or {}).get("centerline", [])),
        "exit": _points((centerlines.get("PitExitAccessCenterline") or {}).get("centerline", [])),
    }


def _sample_to_payload(sample: Any, index: int) -> Optional[Dict[str, Any]]:
    if hasattr(sample, "worldPositionX") and hasattr(sample, "worldPositionZ"):
        point = (float(sample.worldPositionX), -float(sample.worldPositionZ))
        timestamp = getattr(sample, "timestamp", None)
    elif isinstance(sample, dict):
        point = _point(sample.get("mapPosition") or sample.get("point"))
        if point is None and ("x" in sample or "z" in sample):
            point = _point({"x": sample.get("x"), "y": sample.get("y", sample.get("z"))})
        timestamp = sample.get("timestamp") or sample.get("sessionTime")
    else:
        return None
    if point is None:
        return None
    return {
        "index": int(sample.get("index", index)) if isinstance(sample, dict) else index,
        "timestamp": str(timestamp if timestamp is not None else index),
        "mapPosition": point,
    }


def _classify_samples(samples: Sequence[Any], scene: Dict[str, Any]) -> List[Dict[str, Any]]:
    classifier = PitAreaDebugClassifier(scene)
    classified: List[Dict[str, Any]] = []
    for index, raw_sample in enumerate(samples):
        sample = _sample_to_payload(raw_sample, index)
        if sample is None:
            continue
        result = classifier.classify(sample["mapPosition"])
        classified.append(
            {
                "index": sample["index"],
                "timestamp": sample["timestamp"],
                "mapPosition": _point_payload(sample["mapPosition"]),
                **result,
            }
        )
    return classified


def _counts(classified: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    area_counts = {
        "main_track": 0,
        "pit_entry_access": 0,
        "pit_corridor": 0,
        "pit_exit_access": 0,
        "pit_area_other": 0,
        "unknown": 0,
    }
    for item in classified:
        area_counts[item["areaClassification"]] = area_counts.get(item["areaClassification"], 0) + 1
    return area_counts


def _transition_sequence(classified: Sequence[Dict[str, Any]]) -> List[str]:
    sequence: List[str] = []
    for item in classified:
        area = item["areaClassification"]
        if not sequence or sequence[-1] != area:
            sequence.append(area)
    return sequence


def _exit_validated(classified: Sequence[Dict[str, Any]]) -> bool:
    seen_exit = False
    for item in classified:
        area = item["areaClassification"]
        if area == "pit_exit_access":
            seen_exit = True
        if seen_exit and area == "main_track":
            return True
    return False


def _near_exit_subset(classified: Sequence[Dict[str, Any]], radius: float = 135.0) -> List[Dict[str, Any]]:
    return [
        item
        for item in classified
        if item["distanceToExitAccess"] is not None and item["distanceToExitAccess"] <= radius
    ]


def _bounds(points: Iterable[Point], pad: float = 0.0) -> Dict[str, float]:
    pts = [point for point in points if math.isfinite(point[0]) and math.isfinite(point[1])]
    if not pts:
        pts = [(0.0, 0.0), (1.0, 1.0)]
    xs = [point[0] for point in pts]
    ys = [point[1] for point in pts]
    return {"minX": min(xs) - pad, "maxX": max(xs) + pad, "minY": min(ys) - pad, "maxY": max(ys) + pad}


def _svg_transform(view: Dict[str, float], width: int, height: int, margin: int):
    scale = min(
        (width - margin * 2) / max(view["maxX"] - view["minX"], 1.0),
        (height - margin * 2) / max(view["maxY"] - view["minY"], 1.0),
    )

    def transform(point: Point) -> Tuple[float, float]:
        return (
            margin + (point[0] - view["minX"]) * scale,
            height - margin - (point[1] - view["minY"]) * scale,
        )

    return transform


def _svg_path(points: Sequence[Point], transform, *, close: bool = False) -> str:
    if not points:
        return ""
    screen = [transform(point) for point in points]
    commands = [f"M {screen[0][0]:.2f} {screen[0][1]:.2f}"]
    commands.extend(f"L {x:.2f} {y:.2f}" for x, y in screen[1:])
    if close:
        commands.append("Z")
    return " ".join(commands)


def _write_svg(path: Path, scene: Dict[str, Any], classified: Sequence[Dict[str, Any]], title: str) -> None:
    width, height, margin = 1400, 900, 38
    path_points = [(item["mapPosition"]["x"], item["mapPosition"]["y"]) for item in classified]
    view = _bounds([*scene["mainTrack"], *scene["corridor"], *scene["exit"], *path_points], pad=42.0)
    transform = _svg_transform(view, width, height, margin)
    colors = {
        "main_track": "#cbd5e1",
        "pit_entry_access": "#22c55e",
        "pit_corridor": "#facc15",
        "pit_exit_access": "#fb923c",
        "pit_area_other": "#eab308",
        "unknown": "#94a3b8",
    }
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#070a12"/>',
        f'<text x="24" y="30" fill="#e2e8f0" font-family="Consolas, monospace" font-size="15">{title}</text>',
        '<text x="24" y="50" fill="#94a3b8" font-family="Consolas, monospace" font-size="11">debug-only; car mapPosition unchanged</text>',
        f'<path d="{_svg_path(scene["mainTrack"], transform, close=True)}" fill="none" stroke="#8b949e" stroke-width="1.2" opacity="0.52"/>',
        f'<path d="{_svg_path(scene["fastLane"], transform, close=True)}" fill="none" stroke="#a855f7" stroke-width="1" stroke-dasharray="8 8" opacity="0.46"/>',
        f'<path d="{_svg_path(scene["pitLaneAi"], transform)}" fill="none" stroke="#22d3ee" stroke-width="1.4" stroke-dasharray="8 7" opacity="0.75"/>',
        f'<path d="{_svg_path(scene["corridor"], transform)}" fill="none" stroke="#fde047" stroke-width="3.4" opacity="0.92"/>',
        f'<path d="{_svg_path(scene["entry"], transform)}" fill="none" stroke="#22c55e" stroke-width="2.8" opacity="0.76"/>',
        f'<path d="{_svg_path(scene["exit"], transform)}" fill="none" stroke="#fb923c" stroke-width="4.2" opacity="0.98"/>',
    ]
    if path_points:
        parts.append(f'<path d="{_svg_path(path_points, transform)}" fill="none" stroke="#e2e8f0" stroke-width="0.8" opacity="0.30"/>')
    for item in _decimate(classified, 1400):
        point = (item["mapPosition"]["x"], item["mapPosition"]["y"])
        x, y = transform(point)
        color = colors.get(item["areaClassification"], "#94a3b8")
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.0" fill="{color}" opacity="0.75"/>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def _report_payload(classified: Sequence[Dict[str, Any]], source: str) -> Dict[str, Any]:
    counts = _counts(classified)
    sequence = _transition_sequence(classified)
    had_exit_samples = counts.get("pit_exit_access", 0) > 0
    exit_validated = _exit_validated(classified)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "samplesAnalyzed": len(classified),
        "samplesInsideExitAccess": counts.get("pit_exit_access", 0),
        "samplesInsidePitCorridor": counts.get("pit_corridor", 0),
        "samplesOnMainTrack": counts.get("main_track", 0),
        "ambiguousSamples": counts.get("unknown", 0),
        "classificationCounts": counts,
        "transitionSequence": sequence,
        "hadSamplesInsideExitAccess": had_exit_samples,
        "carPassedVisuallyThroughExitAccess": had_exit_samples,
        "exitAccessValidated": exit_validated,
        "changedPitCorridorToPitExitToMainTrack": "pit_corridor" in sequence and "pit_exit_access" in sequence and exit_validated,
        "unknownOrAmbiguousInExit": counts.get("unknown", 0) > 0,
        "runtimeChanged": False,
        "readyForRuntimeIntegration": False,
        "answers": {
            "houveAmostrasDentroDoExitAccess": had_exit_samples,
            "carroPassouVisualmentePeloExitAccess": had_exit_samples,
            "classificacaoMudouPitCorridorPitExitMainTrack": "pit_corridor" in sequence and "pit_exit_access" in sequence and exit_validated,
            "houveAmbiguidadeUnknownNaSaida": counts.get("unknown", 0) > 0,
        },
    }


def export_exit_access_live_validation(repo_root: Path, samples: Sequence[Any], *, source: str = "live_buffer") -> Dict[str, Any]:
    debug_dir = repo_root / "data" / "debug"
    scene = _load_scene(repo_root)
    classified = _classify_samples(samples, scene)
    near_exit = _near_exit_subset(classified)
    payload = {
        **_report_payload(near_exit, source),
        "nearExitRadiusMeters": 135.0,
        "samples": near_exit,
    }
    _write_json(debug_dir / EXIT_LIVE_VALIDATION_JSON, payload)
    _write_svg(debug_dir / EXIT_LIVE_VALIDATION_SVG, scene, near_exit, "PitArea Exit Access live validation")
    _write_json(debug_dir / EXIT_VALIDATION_REPORT_JSON, _report_payload(near_exit, source))
    return payload


def export_recorded_car_path(repo_root: Path, samples: Sequence[Any], *, source: str = "frontend_recording") -> Dict[str, Any]:
    debug_dir = repo_root / "data" / "debug"
    scene = _load_scene(repo_root)
    classified = _classify_samples(samples, scene)
    payload = {
        **_report_payload(classified, source),
        "samples": classified,
    }
    _write_json(debug_dir / RECORDED_CAR_PATH_JSON, payload)
    _write_svg(debug_dir / RECORDED_CAR_PATH_SVG, scene, classified, "PitArea recorded car path")
    exit_report = _report_payload(_near_exit_subset(classified), source)
    _write_json(debug_dir / EXIT_VALIDATION_REPORT_JSON, exit_report)
    return payload
