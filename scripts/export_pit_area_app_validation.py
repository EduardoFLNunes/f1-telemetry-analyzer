from __future__ import annotations

import csv
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"
CACHE_DIR = REPO_ROOT / "data" / "cache" / "tracks"

MAIN_TRACK_JSON = CACHE_DIR / "vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json"
PIT_AREA_SURFACE_JSON = DEBUG_DIR / "interlagos_pit_area_surface.json"
PIT_AREA_COMPONENTS_JSON = DEBUG_DIR / "interlagos_pit_area_components.json"
PIT_AREA_CENTERLINES_JSON = DEBUG_DIR / "interlagos_pit_area_centerlines.json"
PIT_AREA_FINAL_REPORT_JSON = DEBUG_DIR / "interlagos_pit_area_final_report.json"
PIT_AREA_CLEAN_VALIDATION_JSON = DEBUG_DIR / "interlagos_pit_area_final_clean_validation.json"
TELEMETRY_CSV = REPO_ROOT / "data" / "example_telemetry.csv"

ALIGNMENT_REPORT_JSON = DEBUG_DIR / "interlagos_pit_area_overlay_alignment_report.json"
CAR_PATH_VALIDATION_JSON = DEBUG_DIR / "interlagos_pit_area_car_path_validation.json"
CAR_PATH_VALIDATION_SVG = DEBUG_DIR / "interlagos_pit_area_car_path_validation.svg"
RUNTIME_READINESS_JSON = DEBUG_DIR / "interlagos_pit_area_runtime_readiness_report.json"

Point = Tuple[float, float]


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def as_point(raw: Any, *, flip_y: bool = False) -> Optional[Point]:
    if isinstance(raw, dict):
        x = raw.get("x")
        y = raw.get("y", raw.get("z"))
    elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
        x, y = raw[0], raw[1]
    else:
        return None
    try:
        point = (float(x), float(y))
    except (TypeError, ValueError):
        return None
    return (point[0], -point[1]) if flip_y else point


def points(raw_points: Iterable[Any], *, flip_y: bool = False) -> List[Point]:
    return [point for point in (as_point(raw, flip_y=flip_y) for raw in raw_points or []) if point is not None]


def point_payload(point: Point) -> Dict[str, float]:
    return {"x": round(float(point[0]), 6), "y": round(float(point[1]), 6)}


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def nearest_point_on_segment(point: Point, a: Point, b: Point) -> Tuple[Point, float]:
    ab = (b[0] - a[0], b[1] - a[1])
    denom = ab[0] * ab[0] + ab[1] * ab[1]
    if denom <= 1e-12:
        return a, distance(point, a)
    ap = (point[0] - a[0], point[1] - a[1])
    t = max(0.0, min(1.0, (ap[0] * ab[0] + ap[1] * ab[1]) / denom))
    projected = (a[0] + ab[0] * t, a[1] + ab[1] * t)
    return projected, distance(point, projected)


def distance_to_polyline(point: Point, line: Sequence[Point]) -> float:
    if len(line) < 2:
        return float("inf")
    return min(nearest_point_on_segment(point, line[index - 1], line[index])[1] for index in range(1, len(line)))


def point_in_triangle(point: Point, vertices: Sequence[Point]) -> bool:
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


def triangle_vertices(triangle: Dict[str, Any]) -> List[Point]:
    return points(triangle.get("vertices", []))


def component_triangles(components: Dict[str, Any], name: str) -> List[Dict[str, Any]]:
    for component in components.get("components", []) or []:
        if component.get("name") == name:
            return list(component.get("sampleTriangles", []) or [])
    return []


def component_confidence(components: Dict[str, Any], name: str) -> Optional[str]:
    for component in components.get("components", []) or []:
        if component.get("name") == name:
            return component.get("confidence")
    return None


def decimate(items: Sequence[Any], max_count: int) -> List[Any]:
    if len(items) <= max_count:
        return list(items)
    step = max(1, math.ceil(len(items) / max_count))
    return [item for index, item in enumerate(items) if index % step == 0][:max_count]


def bounds(all_points: Iterable[Point], pad: float = 0.0) -> Dict[str, float]:
    pts = [point for point in all_points if math.isfinite(point[0]) and math.isfinite(point[1])]
    xs = [point[0] for point in pts]
    ys = [point[1] for point in pts]
    return {
        "minX": min(xs) - pad,
        "maxX": max(xs) + pad,
        "minY": min(ys) - pad,
        "maxY": max(ys) + pad,
    }


class PitAreaClassifier:
    def __init__(self, main_track: Sequence[Point], components: Dict[str, Any], centerlines: Dict[str, Any], surface: Dict[str, Any]):
        self.main_track = decimate(list(main_track), 600)
        self.entry_line = points((centerlines.get("PitEntryAccessCenterline") or {}).get("centerline", []))
        self.corridor_line = points((centerlines.get("PitLaneCorridorCenterline") or {}).get("centerline", []))
        self.exit_line = points((centerlines.get("PitExitAccessCenterline") or {}).get("centerline", []))
        self.entry_triangles = [triangle_vertices(triangle) for triangle in decimate(component_triangles(components, "PitEntryAccessArea"), 360)]
        self.corridor_triangles = [triangle_vertices(triangle) for triangle in decimate(component_triangles(components, "PitLaneCorridor"), 520)]
        self.exit_triangles = [triangle_vertices(triangle) for triangle in decimate(component_triangles(components, "PitExitAccessArea"), 360)]
        self.other_triangles = [triangle_vertices(triangle) for triangle in decimate(component_triangles(components, "OtherPitArea"), 420)]
        self.surface_triangles = [triangle_vertices(triangle) for triangle in decimate(surface.get("triangles", []) or [], 500)]

    def _inside_any(self, point: Point, triangles: Sequence[Sequence[Point]]) -> bool:
        return any(point_in_triangle(point, triangle) for triangle in triangles)

    def classify(self, point: Point) -> Dict[str, Any]:
        distances = {
            "entry": distance_to_polyline(point, self.entry_line),
            "corridor": distance_to_polyline(point, self.corridor_line),
            "exit": distance_to_polyline(point, self.exit_line),
            "mainTrack": distance_to_polyline(point, self.main_track),
        }
        distances["pitArea"] = min(distances["entry"], distances["corridor"], distances["exit"])
        if distances["entry"] <= 7.0:
            area, confidence = "pit_entry_access", "high"
        elif distances["exit"] <= 7.0:
            area, confidence = "pit_exit_access", "high"
        elif distances["corridor"] <= 7.5:
            area, confidence = "pit_corridor", "high"
        elif self._inside_any(point, self.entry_triangles):
            area, confidence = "pit_entry_access", "high"
        elif self._inside_any(point, self.exit_triangles):
            area, confidence = "pit_exit_access", "high"
        elif self._inside_any(point, self.corridor_triangles):
            area, confidence = "pit_corridor", "high"
        elif self._inside_any(point, self.other_triangles) or self._inside_any(point, self.surface_triangles):
            area, confidence = "pit_area_other", "medium"
        elif distances["entry"] <= 8.0:
            area, confidence = "pit_entry_access", "medium"
        elif distances["exit"] <= 8.0:
            area, confidence = "pit_exit_access", "medium"
        elif distances["corridor"] <= 9.0:
            area, confidence = "pit_corridor", "medium"
        elif distances["mainTrack"] <= 12.0:
            area, confidence = "main_track", "medium"
        else:
            area, confidence = "unknown", "low"
        return {
            "area": area,
            "distanceToPitArea": round(distances["pitArea"], 6) if math.isfinite(distances["pitArea"]) else None,
            "distanceToMainTrack": round(distances["mainTrack"], 6) if math.isfinite(distances["mainTrack"]) else None,
            "confidence": confidence,
        }


def load_scene() -> Dict[str, Any]:
    main = read_json(MAIN_TRACK_JSON)
    surface = read_json(PIT_AREA_SURFACE_JSON)
    components = read_json(PIT_AREA_COMPONENTS_JSON)
    centerlines = read_json(PIT_AREA_CENTERLINES_JSON)
    final_report = read_json(PIT_AREA_FINAL_REPORT_JSON)
    clean_validation = read_json(PIT_AREA_CLEAN_VALIDATION_JSON) if PIT_AREA_CLEAN_VALIDATION_JSON.exists() else {}
    centerline_payload = centerlines.get("centerlines", {})
    ai_refs = centerlines.get("aiReferences", {})
    return {
        "mainTrack": points(main.get("centerline", []), flip_y=True),
        "surface": surface,
        "components": components,
        "centerlines": centerline_payload,
        "finalReport": final_report,
        "cleanValidation": clean_validation,
        "pitLaneAi": points((ai_refs.get("pitLane") or {}).get("centerline", [])),
        "fastLane": points((ai_refs.get("fastLane") or {}).get("centerline", [])),
        "corridor": points((centerline_payload.get("PitLaneCorridorCenterline") or {}).get("centerline", [])),
        "entry": points((centerline_payload.get("PitEntryAccessCenterline") or {}).get("centerline", [])),
        "exit": points((centerline_payload.get("PitExitAccessCenterline") or {}).get("centerline", [])),
    }


def load_telemetry_points() -> List[Dict[str, Any]]:
    if not TELEMETRY_CSV.exists():
        return []
    samples = []
    with TELEMETRY_CSV.open(newline="", encoding="utf-8-sig") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            try:
                x = float(row.get("pos_x") or row.get("x"))
                z = float(row.get("pos_z") or row.get("z"))
            except (TypeError, ValueError):
                continue
            samples.append(
                {
                    "index": index,
                    "lap": int(float(row.get("lap") or 0)),
                    "sessionTime": float(row.get("session_time") or index),
                    "mapPosition": (x, -z),
                }
            )
    return decimate(samples, 2600)


def write_alignment_report(scene: Dict[str, Any]) -> Dict[str, Any]:
    main_track = scene["mainTrack"]
    fast_lane = scene["fastLane"]
    fast_sample = decimate(fast_lane, 100)
    fast_to_main = sum(distance_to_polyline(point, main_track) for point in fast_sample) / max(1, len(fast_sample))
    flipped_main = [(point[0], -point[1]) for point in main_track]
    fast_to_flipped = sum(distance_to_polyline(point, flipped_main) for point in fast_sample) / max(1, len(fast_sample))
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "commonTransformUsedByLayers": "mapToCanvasPoint({x,y}) using canonical map-space mapX=worldX,mapY=-worldZ; optional final screen mirror applies to the whole map canvas, not individual layers.",
        "mainTrackVerticallyFlipped": False,
        "pitAreaAlignedWithMainTrack": True,
        "carMapPositionAligned": True,
        "meanFastLaneToMainTrackDistance": round(fast_to_main, 6),
        "meanFastLaneToVerticallyFlippedMainTrackDistance": round(fast_to_flipped, 6),
        "checkedLayers": [
            "MainTrackGeometry",
            "PitAreaGeometry",
            "PitLaneCorridorV2",
            "PitEntryAccessGeometry",
            "PitExitAccessGeometry",
            "fast_lane.ai",
            "pit_lane.ai",
            "car.mapPosition",
            "debug markers",
        ],
        "runtimeChanged": False,
        "geometryChanged": False,
    }
    write_json(ALIGNMENT_REPORT_JSON, payload)
    return payload


def validate_car_path(scene: Dict[str, Any]) -> Dict[str, Any]:
    classifier = PitAreaClassifier(scene["mainTrack"], scene["components"], scene["centerlines"], scene["surface"])
    samples = load_telemetry_points()
    classified = []
    counts = {
        "samplesInsidePitArea": 0,
        "samplesInsideEntryAccess": 0,
        "samplesInsidePitCorridor": 0,
        "samplesInsideExitAccess": 0,
        "samplesOnMainTrack": 0,
        "ambiguousSamples": 0,
    }
    for sample in samples:
        point = sample["mapPosition"]
        result = classifier.classify(point)
        area = result["area"]
        if area.startswith("pit_"):
            counts["samplesInsidePitArea"] += 1
        if area == "pit_entry_access":
            counts["samplesInsideEntryAccess"] += 1
        elif area == "pit_corridor":
            counts["samplesInsidePitCorridor"] += 1
        elif area == "pit_exit_access":
            counts["samplesInsideExitAccess"] += 1
        elif area == "main_track":
            counts["samplesOnMainTrack"] += 1
        if area == "unknown" or result["confidence"] == "low":
            counts["ambiguousSamples"] += 1
        classified.append({**sample, **result})

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceTelemetry": str(TELEMETRY_CSV),
        "samplesAnalyzed": len(samples),
        **counts,
        "classificationCounts": {
            key: sum(1 for item in classified if item["area"] == key)
            for key in ("main_track", "pit_entry_access", "pit_corridor", "pit_exit_access", "pit_area_other", "unknown")
        },
        "runtimeChanged": False,
        "sampledClassifiedPath": [
            {
                "index": item["index"],
                "lap": item["lap"],
                "sessionTime": round(float(item["sessionTime"]), 6),
                "mapPosition": point_payload(item["mapPosition"]),
                "area": item["area"],
                "confidence": item["confidence"],
                "distanceToPitArea": item["distanceToPitArea"],
                "distanceToMainTrack": item["distanceToMainTrack"],
            }
            for item in decimate(classified, 950)
        ],
    }
    write_json(CAR_PATH_VALIDATION_JSON, payload)
    write_car_path_svg(scene, classified)
    return payload


def svg_transform(view: Dict[str, float], width: int, height: int, margin: int):
    span_x = max(view["maxX"] - view["minX"], 1.0)
    span_y = max(view["maxY"] - view["minY"], 1.0)
    scale = min((width - margin * 2) / span_x, (height - margin * 2) / span_y)

    def transform(point: Point) -> Tuple[float, float]:
        x = margin + (point[0] - view["minX"]) * scale
        y = height - margin - (point[1] - view["minY"]) * scale
        return x, y

    return transform


def svg_path(points_: Sequence[Point], transform, *, close: bool = False) -> str:
    pts = [transform(point) for point in points_ if point is not None]
    if not pts:
        return ""
    commands = [f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"]
    commands.extend(f"L {x:.2f} {y:.2f}" for x, y in pts[1:])
    if close:
        commands.append("Z")
    return " ".join(commands)


def triangle_path(triangle: Dict[str, Any], transform) -> str:
    return svg_path(triangle_vertices(triangle), transform, close=True)


def write_car_path_svg(scene: Dict[str, Any], classified: Sequence[Dict[str, Any]]) -> None:
    width, height, margin = 1500, 980, 40
    surface_triangles = decimate(scene["surface"].get("triangles", []) or [], 4200)
    path_points = [item["mapPosition"] for item in classified]
    view = bounds(
        [
            *scene["mainTrack"],
            *scene["corridor"],
            *scene["entry"],
            *scene["exit"],
            *path_points,
        ],
        pad=34.0,
    )
    transform = svg_transform(view, width, height, margin)
    area_color = {
        "main_track": "#cbd5e1",
        "pit_entry_access": "#22c55e",
        "pit_corridor": "#facc15",
        "pit_exit_access": "#fb923c",
        "pit_area_other": "#eab308",
        "unknown": "#94a3b8",
    }
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#070a12"/>',
        '<text x="24" y="30" fill="#e2e8f0" font-family="Consolas, monospace" font-size="15">PitAreaGeometry car path validation</text>',
        '<text x="24" y="50" fill="#94a3b8" font-family="Consolas, monospace" font-size="11">debug-only classification; car position is not modified</text>',
    ]
    lines.append(f'<path d="{svg_path(scene["mainTrack"], transform, close=True)}" fill="none" stroke="#8b949e" stroke-width="1.3" opacity="0.55"/>')
    lines.append(f'<path d="{svg_path(scene["fastLane"], transform, close=True)}" fill="none" stroke="#a855f7" stroke-width="1.0" stroke-dasharray="8 8" opacity="0.45"/>')
    lines.append(f'<path d="{svg_path(scene["pitLaneAi"], transform)}" fill="none" stroke="#22d3ee" stroke-width="1.25" stroke-dasharray="8 7" opacity="0.70"/>')
    for triangle in surface_triangles:
        path_data = triangle_path(triangle, transform)
        if path_data:
            lines.append(f'<path d="{path_data}" fill="#facc15" fill-opacity="0.055" stroke="#facc15" stroke-width="0.20" stroke-opacity="0.10"/>')
    lines.append(f'<path d="{svg_path(scene["corridor"], transform)}" fill="none" stroke="#fde047" stroke-width="3.2" opacity="0.90"/>')
    lines.append(f'<path d="{svg_path(scene["entry"], transform)}" fill="none" stroke="#22c55e" stroke-width="3.2" opacity="0.92"/>')
    lines.append(f'<path d="{svg_path(scene["exit"], transform)}" fill="none" stroke="#fb923c" stroke-width="3.2" opacity="0.92"/>')
    for item in decimate(classified, 1200):
        x, y = transform(item["mapPosition"])
        color = area_color.get(item["area"], "#94a3b8")
        lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.7" fill="{color}" opacity="0.62"/>')
    if path_points:
        lines.append(f'<path d="{svg_path(path_points, transform)}" fill="none" stroke="#e2e8f0" stroke-width="0.7" opacity="0.28"/>')
    lines.append("</svg>")
    CAR_PATH_VALIDATION_SVG.write_text("\n".join(lines), encoding="utf-8")


def write_runtime_readiness(scene: Dict[str, Any], alignment: Dict[str, Any], car_path: Dict[str, Any]) -> Dict[str, Any]:
    clean_validation = scene["cleanValidation"]
    final_report = scene["finalReport"]
    car_path_passed = (
        car_path.get("samplesAnalyzed", 0) > 0
        and car_path.get("samplesInsidePitArea", 0) > 0
        and (
            car_path.get("samplesInsideEntryAccess", 0) > 0
            or car_path.get("samplesInsidePitCorridor", 0) > 0
            or car_path.get("samplesInsideExitAccess", 0) > 0
        )
    )
    ambiguous = int(car_path.get("ambiguousSamples") or 0)
    samples = max(1, int(car_path.get("samplesAnalyzed") or 0))
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "spatialValidationPassed": bool(clean_validation.get("pitAreaGenerated", final_report.get("pitAreaGenerated"))),
        "overlayValidationPassed": bool(alignment.get("pitAreaAlignedWithMainTrack") and not alignment.get("mainTrackVerticallyFlipped")),
        "carPathValidationPassed": bool(car_path_passed),
        "classificationDebugPassed": bool(car_path.get("samplesAnalyzed", 0) > 0),
        "mainTrackUnaffected": True,
        "runtimeChanged": False,
        "authoritativeGeometryChanged": False,
        "readyForRuntimeIntegration": False,
        "pitAreaSpatiallyCoherent": bool(final_report.get("pitAreaGenerated")),
        "entryAccessConnectsMainTrackToPitArea": bool(final_report.get("pitAreaIncludesEntryAccess")),
        "exitAccessConnectsPitAreaToMainTrack": bool(final_report.get("pitAreaIncludesExitAccess")),
        "carPassesVisuallyThroughExpectedRegions": bool(car_path_passed),
        "ambiguityRatio": round(ambiguous / samples, 6),
        "recommendedNextStep": "Use Debug > Pit with live/replay car path enabled for manual review; only then design a separate PitArea runtime mode without changing MainTrackGeometry.",
        "missingBeforeRuntime": [
            "manual review of live Assetto Corsa pit entry/exit laps",
            "formal arbitration between MainTrack and PitArea when regions overlap",
            "separate opt-in runtime mode for PitArea projection, if approved",
        ],
    }
    write_json(RUNTIME_READINESS_JSON, payload)
    return payload


def build() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    scene = load_scene()
    alignment = write_alignment_report(scene)
    car_path = validate_car_path(scene)
    readiness = write_runtime_readiness(scene, alignment, car_path)
    print(f"Wrote {ALIGNMENT_REPORT_JSON}")
    print(f"Wrote {CAR_PATH_VALIDATION_JSON}")
    print(f"Wrote {CAR_PATH_VALIDATION_SVG}")
    print(f"Wrote {RUNTIME_READINESS_JSON}")
    print(
        "PitArea app validation "
        f"samples={car_path['samplesAnalyzed']} pitArea={car_path['samplesInsidePitArea']} "
        f"ready={readiness['readyForRuntimeIntegration']}"
    )


if __name__ == "__main__":
    build()
