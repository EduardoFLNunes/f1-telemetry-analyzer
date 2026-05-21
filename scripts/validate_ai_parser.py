from __future__ import annotations

import json
import math
import struct
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.kn5.track_surface_polygon import build_track_surface_polygon_from_manifest  # noqa: E402
from core.track_file_resolver import TrackFileResolver  # noqa: E402


Point = Tuple[float, float]


PARSER_CANDIDATES = [
    {
        "name": "ac_spline_block20_header16",
        "description": "AC spline position block: header 16 bytes, each point x/y/z/distance/rawIndex with 20-byte stride.",
        "headerOffset": 16,
        "pointStride": 20,
        "countMode": "declared",
        "kind": "block20",
        "xOffsetBytes": 0,
        "yOffsetBytes": 4,
        "zOffsetBytes": 8,
        "distanceOffsetBytes": 12,
        "indexOffsetBytes": 16,
    },
    {
        "name": "legacy_18f_header8_declared",
        "description": "Legacy/debug parser currently seen in old pitlane scripts: skip 8-byte header, then read 18 floats per declared point.",
        "headerOffset": 8,
        "pointStride": 72,
        "countMode": "declared",
        "kind": "18f",
        "xOffsetBytes": 0,
        "yOffsetBytes": 4,
        "zOffsetBytes": 8,
    },
    {
        "name": "legacy_18f_header8_until_eof",
        "description": "Legacy/debug parser when it reads 18-float chunks until EOF; this explains the 1739 pit_lane.ai count.",
        "headerOffset": 8,
        "pointStride": 72,
        "countMode": "until_eof",
        "kind": "18f",
        "xOffsetBytes": 0,
        "yOffsetBytes": 4,
        "zOffsetBytes": 8,
    },
    {
        "name": "secondary_18f_after_block20_plus8",
        "description": "Secondary 18-float block after the position block and 8 extra bytes; inspected only as a candidate, not used for map geometry.",
        "headerOffset": "16 + declaredPointCount * 20 + 8",
        "pointStride": 72,
        "countMode": "declared",
        "kind": "18f_after_block20",
        "xOffsetBytes": 0,
        "yOffsetBytes": 4,
        "zOffsetBytes": 8,
    },
]


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _round_point(point: Sequence[float]) -> List[float]:
    return [_round(point[0]), _round(point[1])]


def _xml(value: Any) -> str:
    return escape(str(value), quote=False)


def _bounds(points: Iterable[Sequence[float]]) -> Optional[Dict[str, float]]:
    values = [(float(point[0]), float(point[1])) for point in points]
    if not values:
        return None
    xs = [point[0] for point in values]
    ys = [point[1] for point in values]
    return {
        "minX": _round(min(xs)),
        "maxX": _round(max(xs)),
        "minY": _round(min(ys)),
        "maxY": _round(max(ys)),
        "width": _round(max(xs) - min(xs)),
        "height": _round(max(ys) - min(ys)),
    }


def _bbox_overlap(a: Optional[Dict[str, float]], b: Optional[Dict[str, float]]) -> Dict[str, float]:
    if not a or not b:
        return {"area": 0.0, "ratioA": 0.0, "ratioB": 0.0}
    width = max(0.0, min(a["maxX"], b["maxX"]) - max(a["minX"], b["minX"]))
    height = max(0.0, min(a["maxY"], b["maxY"]) - max(a["minY"], b["minY"]))
    area = width * height
    area_a = max(1e-9, float(a["width"]) * float(a["height"]))
    area_b = max(1e-9, float(b["width"]) * float(b["height"]))
    return {"area": _round(area), "ratioA": _round(area / area_a), "ratioB": _round(area / area_b)}


def _stats(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {"min": 0.0, "avg": 0.0, "p95": 0.0, "max": 0.0}
    sorted_values = sorted(float(value) for value in values)
    p95_index = min(len(sorted_values) - 1, max(0, math.ceil(len(sorted_values) * 0.95) - 1))
    return {
        "min": _round(sorted_values[0]),
        "avg": _round(sum(sorted_values) / len(sorted_values)),
        "p95": _round(sorted_values[p95_index]),
        "max": _round(sorted_values[-1]),
    }


def _segment_stats(points: Sequence[Point]) -> Dict[str, float]:
    distances = [
        math.hypot(points[index + 1][0] - points[index][0], points[index + 1][1] - points[index][1])
        for index in range(len(points) - 1)
    ]
    return _stats(distances)


def _resolved_offset(candidate: Dict[str, Any], declared_count: int) -> int:
    if candidate["kind"] == "18f_after_block20":
        return 16 + declared_count * 20 + 8
    return int(candidate["headerOffset"])


def _candidate_count(candidate: Dict[str, Any], data_size: int, declared_count: int) -> int:
    offset = _resolved_offset(candidate, declared_count)
    stride = int(candidate["pointStride"])
    if offset >= data_size:
        return 0
    if candidate["countMode"] == "until_eof":
        return max(0, (data_size - offset) // stride)
    return min(declared_count, max(0, (data_size - offset) // stride))


def _parse_candidate(data: bytes, candidate: Dict[str, Any], declared_count: int) -> Dict[str, Any]:
    offset = _resolved_offset(candidate, declared_count)
    stride = int(candidate["pointStride"])
    count = _candidate_count(candidate, len(data), declared_count)
    points: List[Dict[str, Any]] = []
    map_points: List[Point] = []

    for index in range(count):
        point_offset = offset + index * stride
        if point_offset + stride > len(data):
            break
        if candidate["kind"] == "block20":
            x, y, z, distance, raw_index = struct.unpack_from("<3f f I", data, point_offset)
            raw_values: List[Any] = [_round(x), _round(y), _round(z), _round(distance), int(raw_index)]
        else:
            floats = list(struct.unpack_from("<18f", data, point_offset))
            x, y, z = floats[0], floats[1], floats[2]
            distance = None
            raw_index = None
            raw_values = [_round(value) for value in floats[:18]]
        map_point = (float(x), float(-z))
        map_points.append(map_point)
        if index < 10 or index >= count - 10:
            row: Dict[str, Any] = {
                "index": index,
                "fileOffset": point_offset,
                "rawValues": raw_values,
                "worldPosition": [_round(x), _round(y), _round(z)],
                "mapPosition": _round_point(map_point),
            }
            if distance is not None:
                row["distance"] = _round(float(distance))
            if raw_index is not None:
                row["rawIndex"] = int(raw_index)
            points.append(row)

    expected_first_block_size = offset + count * stride
    return {
        "name": candidate["name"],
        "description": candidate["description"],
        "headerOffset": offset,
        "pointStride": stride,
        "countMode": candidate["countMode"],
        "xyzOffsetsBytes": {
            "x": candidate.get("xOffsetBytes"),
            "y": candidate.get("yOffsetBytes"),
            "z": candidate.get("zOffsetBytes"),
        },
        "distanceOffsetBytes": candidate.get("distanceOffsetBytes"),
        "indexOffsetBytes": candidate.get("indexOffsetBytes"),
        "pointCount": count,
        "bytesConsumedByCandidate": expected_first_block_size,
        "trailingBytesAfterCandidate": max(0, len(data) - expected_first_block_size),
        "fitsDeclaredPointCount": count == declared_count if candidate["countMode"] == "declared" else None,
        "bounds": _bounds(map_points),
        "segmentLengthStats": _segment_stats(map_points),
        "first10RawPoints": [point for point in points if point["index"] < 10],
        "last10RawPoints": [point for point in points if point["index"] >= count - 10],
        "mapPoints": map_points,
    }


def inspect_ai_file(path: str) -> Dict[str, Any]:
    ai_path = Path(path)
    data = ai_path.read_bytes()
    if len(data) < 8:
        raise ValueError(f"AI file too small: {ai_path}")
    version, declared_count = struct.unpack_from("<II", data, 0)
    first_u32 = list(struct.unpack_from("<4I", data + b"\0" * max(0, 16 - len(data)), 0)) if len(data) >= 16 else []
    candidates = [_parse_candidate(data, candidate, int(declared_count)) for candidate in PARSER_CANDIDATES]
    return {
        "path": str(ai_path),
        "fileSizeBytes": len(data),
        "first32BytesHex": data[:32].hex(" "),
        "firstU32Values": first_u32,
        "magic": None,
        "magicNote": "No ASCII magic was found; first u32 is treated as version.",
        "version": int(version),
        "declaredPointCount": int(declared_count),
        "headerBytes": {
            "versionOffset": 0,
            "declaredPointCountOffset": 4,
            "reservedOrUnknownOffsets": [8, 12],
        },
        "parserCandidates": [
            {key: value for key, value in candidate.items() if key != "mapPoints"}
            for candidate in candidates
        ],
        "_candidateMapPoints": {candidate["name"]: candidate["mapPoints"] for candidate in candidates},
    }


def _surface_bounds(surface: Dict[str, Any]) -> Optional[Dict[str, float]]:
    points: List[Sequence[float]] = []
    for triangle in surface.get("triangles", []):
        points.extend(triangle.get("vertices", []))
    return _bounds(points)


def _load_main_track_geometry(track_name: str, track_config: str) -> Dict[str, Any]:
    cache_path = REPO_ROOT / "data" / "cache" / "tracks" / f"{track_name}_{track_config}_kn5_surface_interval_cleaned_geometry.json"
    if not cache_path.exists():
        return {"path": str(cache_path), "available": False, "centerline": [], "boundsLeft": [], "boundsRight": [], "bounds": None}
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    return {
        "path": str(cache_path),
        "available": True,
        "provider": data.get("provider"),
        "geometrySource": data.get("geometrySource"),
        "centerline": data.get("centerline", []),
        "boundsLeft": data.get("boundsLeft", []),
        "boundsRight": data.get("boundsRight", []),
        "bounds": data.get("bounds"),
        "pointCount": len(data.get("centerline", [])),
    }


def _point_from_track(point: Dict[str, Any]) -> Point:
    return float(point["x"]), float(point.get("y", point.get("z", 0.0)))


def _svg_canvas(bounds: Dict[str, float], width: int = 1400, height: int = 1000, margin: int = 36) -> Dict[str, Any]:
    min_x, max_x = bounds["minX"], bounds["maxX"]
    min_y, max_y = bounds["minY"], bounds["maxY"]
    scale = min((width - margin * 2) / max(1.0, max_x - min_x), (height - margin * 2) / max(1.0, max_y - min_y))

    def sx(point: Sequence[float]) -> Tuple[float, float]:
        x = margin + (float(point[0]) - min_x) * scale
        y = height - margin - (float(point[1]) - min_y) * scale
        return x, y

    return {"sx": sx, "width": width, "height": height}


def _polyline(points: Sequence[Sequence[float]], sx, *, stroke: str, width: float, opacity: float = 1.0, dash: Optional[str] = None) -> str:
    if not points:
        return ""
    point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in (sx(point) for point in points))
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{point_text}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-opacity="{opacity}" stroke-linejoin="round" stroke-linecap="round"{dash_attr}/>'


def _polygon(points: Sequence[Sequence[float]], sx, *, fill: str, opacity: float, stroke: str = "none", width: float = 1.0) -> str:
    if not points:
        return ""
    point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in (sx(point) for point in points))
    return f'<polygon points="{point_text}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{width}"/>'


def build_svg(
    fast_points: Sequence[Point],
    pit_points: Sequence[Point],
    pit_surface: Dict[str, Any],
    main_track: Dict[str, Any],
    metrics: Dict[str, Any],
    output_path: Path,
) -> None:
    all_points: List[Sequence[float]] = list(fast_points) + list(pit_points)
    if main_track.get("centerline"):
        all_points.extend(_point_from_track(point) for point in main_track["centerline"])
    if pit_surface.get("triangles"):
        for triangle in pit_surface["triangles"]:
            all_points.extend(triangle["vertices"])
    bounds = _bounds(all_points) or {"minX": -500, "maxX": 500, "minY": -500, "maxY": 500, "width": 1000, "height": 1000}
    canvas = _svg_canvas(bounds)
    sx = canvas["sx"]
    metric_text = (
        f"pit bbox/main ratio={metrics['pitLaneBBoxVsMainTrack']['ratioA']}, "
        f"pit bbox/pit surface ratio={metrics['pitLaneBBoxVsPitLaneSurface']['ratioA']}, "
        f"likelyInvalid={metrics['pitLaneAiParseLikelyInvalid']}"
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas["width"]}" height="{canvas["height"]}" viewBox="0 0 {canvas["width"]} {canvas["height"]}">',
        '<rect width="100%" height="100%" fill="#080b10"/>',
        '<text x="18" y="28" fill="#e2e8f0" font-size="15" font-family="monospace">AI parser validation: fast_lane.ai vs pit_lane.ai</text>',
        f'<text x="18" y="50" fill="#94a3b8" font-size="11" font-family="monospace">{_xml("parser=ac_spline_block20_header16, map debug transform x,-z; runtime unchanged")}</text>',
        f'<text x="18" y="70" fill="#94a3b8" font-size="11" font-family="monospace">{_xml(metric_text)}</text>',
    ]

    left = [_point_from_track(point) for point in main_track.get("boundsLeft", [])]
    right = [_point_from_track(point) for point in main_track.get("boundsRight", [])]
    if left and right:
        parts.append(_polygon(left + list(reversed(right)), sx, fill="#64748b", opacity=0.18, stroke="#94a3b8", width=0.6))
    elif main_track.get("centerline"):
        parts.append(_polyline([_point_from_track(point) for point in main_track["centerline"]], sx, stroke="#94a3b8", width=1.2, opacity=0.6))

    for triangle in pit_surface.get("triangles", []):
        parts.append(_polygon(triangle["vertices"], sx, fill="#eab308", opacity=0.28))

    parts.append(_polyline(fast_points, sx, stroke="#a855f7", width=2.0, opacity=0.92))
    parts.append(_polyline(pit_points, sx, stroke="#facc15", width=2.4, opacity=0.95, dash="7,5"))

    for point, color, label in ((fast_points[0], "#c084fc", "fast start"), (pit_points[0], "#fde047", "pit start"), (pit_points[-1], "#f97316", "pit end")):
        x, y = sx(point)
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{color}"/>')
        parts.append(f'<text x="{x + 7:.2f}" y="{y - 7:.2f}" fill="{color}" font-size="10" font-family="monospace">{_xml(label)}</text>')

    legend = [
        ("MainTrackGeometry", "#94a3b8"),
        ("PitLaneSurface 1pitlane*", "#eab308"),
        ("fast_lane.ai", "#a855f7"),
        ("pit_lane.ai", "#facc15"),
    ]
    for index, (label, color) in enumerate(legend):
        y = 96 + index * 18
        parts.append(f'<rect x="18" y="{y - 10}" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="34" y="{y}" fill="#cbd5e1" font-size="11" font-family="monospace">{_xml(label)}</text>')

    parts.append("</svg>")
    output_path.write_text("\n".join(part for part in parts if part), encoding="utf-8")


def main() -> None:
    track_name = sys.argv[1] if len(sys.argv) > 1 else "vhe_interlagos"
    track_config = sys.argv[2] if len(sys.argv) > 2 else "gp"
    output_dir = REPO_ROOT / "data" / "debug"
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = TrackFileResolver().build_track_file_manifest(
        track_name,
        track_config,
        source="assetto_corsa",
        game_code="assetto_corsa",
    ).to_dict()
    ai_files = manifest.get("aiFiles") or {}
    fast_path = ai_files.get("fast_lane")
    pit_path = ai_files.get("pit_lane")
    if not fast_path or not pit_path:
        raise FileNotFoundError("TrackFileResolver did not resolve both fast_lane.ai and pit_lane.ai")

    fast = inspect_ai_file(fast_path)
    pit = inspect_ai_file(pit_path)
    fast_points = fast["_candidateMapPoints"]["ac_spline_block20_header16"]
    pit_points = pit["_candidateMapPoints"]["ac_spline_block20_header16"]

    pit_surface = build_track_surface_polygon_from_manifest(manifest, included_surfaces=["PITLANE"])
    main_track = _load_main_track_geometry(track_name, track_config)

    pit_surface_bounds = _surface_bounds(pit_surface)
    main_bounds = main_track.get("bounds")
    fast_bounds = _bounds(fast_points)
    pit_bounds = _bounds(pit_points)
    pit_vs_surface = _bbox_overlap(pit_bounds, pit_surface_bounds)
    pit_vs_main = _bbox_overlap(pit_bounds, main_bounds)
    fast_vs_main = _bbox_overlap(fast_bounds, main_bounds)
    pit_bbox_area = max(1e-9, float((pit_bounds or {}).get("width", 0.0)) * float((pit_bounds or {}).get("height", 0.0)))
    surface_area = max(1e-9, float((pit_surface_bounds or {}).get("width", 0.0)) * float((pit_surface_bounds or {}).get("height", 0.0)))
    main_area = max(1e-9, float((main_bounds or {}).get("width", 0.0)) * float((main_bounds or {}).get("height", 0.0)))
    pit_area_vs_surface = pit_bbox_area / surface_area
    pit_area_vs_main = pit_bbox_area / main_area
    pit_parse_likely_invalid = pit_vs_surface["ratioA"] < 0.25 and pit_area_vs_surface > 5.0

    metrics = {
        "fastLaneBBoxVsMainTrack": fast_vs_main,
        "pitLaneBBoxVsPitLaneSurface": pit_vs_surface,
        "pitLaneBBoxVsMainTrack": pit_vs_main,
        "pitLaneBBoxAreaVsPitLaneSurfaceBBoxArea": _round(pit_area_vs_surface),
        "pitLaneBBoxAreaVsMainTrackBBoxArea": _round(pit_area_vs_main),
        "pitLaneAiParseLikelyInvalid": bool(pit_parse_likely_invalid),
        "pitLaneInterpretation": (
            "Parsed pit_lane.ai does not behave like a pitlane-only centerline; its bbox is much larger than PitLaneSurface."
            if pit_parse_likely_invalid
            else "Parsed pit_lane.ai bbox is compatible with a pitlane-only line."
        ),
    }

    validation = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "trackName": track_name,
        "trackConfig": track_config,
        "runtimeChanged": False,
        "canonicalMapTransformChanged": False,
        "parserUsedForComparison": "ac_spline_block20_header16",
        "manifest": {
            "mainVisual": (manifest.get("candidateGeometryFiles") or {}).get("mainVisual"),
            "fastLaneAi": fast_path,
            "pitLaneAi": pit_path,
            "surfacesIni": manifest.get("surfacesIni"),
        },
        "aiFormatHypothesis": {
            "versionField": "uint32 at byte offset 0",
            "declaredPointCountField": "uint32 at byte offset 4",
            "reservedOrUnknownHeaderBytes": "bytes 8..15 are zero in inspected Interlagos files",
            "positionBlock": "starts at byte 16 with 20-byte records: float32 x, float32 y, float32 z, float32 distance, uint32 rawIndex",
            "legacy18fParserStatus": "invalid for position parsing when started at byte 8; it mixes header/position bytes and explains impossible x=0/y=363 and count 1739.",
        },
        "fastLaneAi": {key: value for key, value in fast.items() if key != "_candidateMapPoints"},
        "pitLaneAi": {key: value for key, value in pit.items() if key != "_candidateMapPoints"},
        "pitLaneSurface": {
            "triangleCount": len(pit_surface.get("triangles", [])),
            "meshCount": pit_surface.get("meshCount"),
            "bounds": pit_surface_bounds,
            "meshes": [
                {
                    "meshName": mesh.get("meshName"),
                    "matchedSurface": mesh.get("matchedSurface"),
                    "capturedTriangles": mesh.get("capturedTriangles"),
                    "bounds": mesh.get("bounds"),
                }
                for mesh in pit_surface.get("meshes", [])
            ],
        },
        "mainTrackGeometry": {
            "available": main_track.get("available"),
            "path": main_track.get("path"),
            "provider": main_track.get("provider"),
            "geometrySource": main_track.get("geometrySource"),
            "pointCount": main_track.get("pointCount"),
            "bounds": main_bounds,
        },
        "comparison": {
            "fastLanePointCount": len(fast_points),
            "pitLanePointCount": len(pit_points),
            "fastLaneBounds": fast_bounds,
            "pitLaneBounds": pit_bounds,
            **metrics,
        },
        "exports": {
            "json": str(output_dir / "ai_parser_validation.json"),
            "svg": str(output_dir / "ai_parser_fast_vs_pit.svg"),
        },
    }

    json_path = output_dir / "ai_parser_validation.json"
    svg_path = output_dir / "ai_parser_fast_vs_pit.svg"
    json_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    build_svg(fast_points, pit_points, pit_surface, main_track, metrics, svg_path)

    print(
        json.dumps(
            {
                "fastLanePointCount": len(fast_points),
                "pitLanePointCount": len(pit_points),
                "pitLaneAiParseLikelyInvalid": bool(pit_parse_likely_invalid),
                "pitLaneBBoxAreaVsPitLaneSurfaceBBoxArea": _round(pit_area_vs_surface),
                "pitLaneBBoxAreaVsMainTrackBBoxArea": _round(pit_area_vs_main),
                "exports": validation["exports"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
