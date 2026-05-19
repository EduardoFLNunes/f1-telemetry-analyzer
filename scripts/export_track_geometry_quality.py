from pathlib import Path
import json
import sys
from typing import Any, Dict, List, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.geometry.track_geometry_cleanup import (  # noqa: E402
    audit_geometry,
    cleanup_geometry,
    distance,
    map_point_from_cache,
    round_point,
    stats,
)


TRACK_CACHE = REPO_ROOT / "data" / "cache" / "tracks" / "vhe_interlagos_gp_kn5_surface_interval_geometry.json"
DEBUG_DIR = REPO_ROOT / "data" / "debug"


def load_track_geometry(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    centerline = [map_point_from_cache(point) for point in data.get("centerline", [])]
    left_edge = [map_point_from_cache(point) for point in data.get("boundsLeft", [])]
    right_edge = [map_point_from_cache(point) for point in data.get("boundsRight", [])]
    widths = [float(width) for width in data.get("localWidth", [])]
    count = min(len(centerline), len(left_edge), len(right_edge), len(widths))
    distances = [float(point.get("distance", 0.0)) for point in data.get("centerline", [])[:count]]
    p_values = [float(point.get("spline_t", index / max(count - 1, 1))) for index, point in enumerate(data.get("centerline", [])[:count])]
    return {
        "raw": data,
        "centerline": centerline[:count],
        "leftEdge": left_edge[:count],
        "rightEdge": right_edge[:count],
        "localWidth": widths[:count],
        "distanceAlongTrack": distances,
        "p": p_values,
    }


def bounds_for_series(series: Sequence[Sequence[float]]) -> Dict[str, float]:
    xs = [float(point[0]) for point in series]
    ys = [float(point[1]) for point in series]
    return {
        "minX": min(xs),
        "maxX": max(xs),
        "minY": min(ys),
        "maxY": max(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
    }


def make_projector(series: Sequence[Sequence[float]], width: int = 1200, height: int = 960, margin: int = 32):
    bounds = bounds_for_series(series)
    scale = min(
        (width - margin * 2) / max(bounds["width"], 1.0),
        (height - margin * 2) / max(bounds["height"], 1.0),
    )

    def project(point: Sequence[float]) -> Tuple[float, float]:
        x = margin + (float(point[0]) - bounds["minX"]) * scale
        y = height - margin - (float(point[1]) - bounds["minY"]) * scale
        return x, y

    return project, width, height


def polyline(points: Sequence[Sequence[float]], project, stroke: str, width: float, opacity: float = 1.0, dash: str = "") -> str:
    if len(points) < 2:
        return ""
    point_text = " ".join(f"{project(point)[0]:.2f},{project(point)[1]:.2f}" for point in points)
    dash_text = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{point_text}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-opacity="{opacity}" stroke-linejoin="round" stroke-linecap="round"{dash_text}/>'


def marker(point: Sequence[float], project, color: str, radius: float = 3.0, opacity: float = 0.9) -> str:
    x, y = project(point)
    return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{color}" fill-opacity="{opacity}"/>'


def write_raw_vs_cleaned_svg(raw: Dict[str, Any], cleaned: Dict[str, Any], path: Path) -> None:
    all_points = raw["centerline"] + raw["leftEdge"] + raw["rightEdge"] + cleaned["centerline"] + cleaned["leftEdge"] + cleaned["rightEdge"]
    project, width, height = make_projector(all_points)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#080b10"/>',
        '<text x="32" y="34" fill="#d9e6f2" font-family="Segoe UI, Arial" font-size="16">Raw vs cleaned KN5 interval geometry</text>',
        polyline(raw["leftEdge"], project, "#7e8796", 0.8, 0.36),
        polyline(raw["rightEdge"], project, "#7e8796", 0.8, 0.36),
        polyline(raw["centerline"], project, "#f4b350", 0.9, 0.45, "4 7"),
        polyline(cleaned["leftEdge"], project, "#4aa3ff", 1.4, 0.9),
        polyline(cleaned["rightEdge"], project, "#ff637d", 1.4, 0.9),
        polyline(cleaned["centerline"], project, "#5dff9a", 1.2, 0.88),
        "</svg>",
    ]
    path.write_text("\n".join(part for part in parts if part), encoding="utf-8")


def write_cleaned_preview_svg(cleaned: Dict[str, Any], path: Path) -> None:
    all_points = cleaned["centerline"] + cleaned["leftEdge"] + cleaned["rightEdge"]
    project, width, height = make_projector(all_points)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#080b10"/>',
        '<text x="32" y="34" fill="#d9e6f2" font-family="Segoe UI, Arial" font-size="16">Cleaned KN5 interval geometry preview</text>',
        polyline(cleaned["leftEdge"], project, "#4aa3ff", 1.8, 0.92),
        polyline(cleaned["rightEdge"], project, "#ff637d", 1.8, 0.92),
        polyline(cleaned["centerline"], project, "#5dff9a", 1.4, 0.86),
        "</svg>",
    ]
    path.write_text("\n".join(part for part in parts if part), encoding="utf-8")


def write_problem_segments_svg(raw: Dict[str, Any], report: Dict[str, Any], path: Path) -> None:
    all_points = raw["centerline"] + raw["leftEdge"] + raw["rightEdge"]
    project, width, height = make_projector(all_points)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#080b10"/>',
        '<text x="32" y="34" fill="#d9e6f2" font-family="Segoe UI, Arial" font-size="16">Problem segment markers</text>',
        polyline(raw["leftEdge"], project, "#4aa3ff", 0.8, 0.35),
        polyline(raw["rightEdge"], project, "#ff637d", 0.8, 0.35),
        polyline(raw["centerline"], project, "#5dff9a", 0.8, 0.35),
    ]
    colors = {
        "centerline": "#ff3b30",
        "leftEdge": "#ffb000",
        "rightEdge": "#ff4f8b",
    }
    for series_name, key in (
        ("centerline", "top50LargestCenterlineJumps"),
        ("leftEdge", "top50LargestLeftEdgeJumps"),
        ("rightEdge", "top50LargestRightEdgeJumps"),
    ):
        for item in report.get(key, [])[:50]:
            start = item["from"]
            end = item["to"]
            x1, y1 = project(start)
            x2, y2 = project(end)
            parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{colors[series_name]}" stroke-width="2.2" stroke-opacity="0.88"/>')
    for item in report.get("samplesBelowWidthLimit", [])[:100]:
        parts.append(marker(item["centerline"], project, "#40e0d0", radius=2.2, opacity=0.8))
    for item in report.get("samplesAboveWidthLimit", [])[:100]:
        parts.append(marker(item["centerline"], project, "#ff3b30", radius=2.6, opacity=0.9))
    parts.append("</svg>")
    path.write_text("\n".join(part for part in parts if part), encoding="utf-8")


def cleaned_payload(raw_data: Dict[str, Any], cleaned: Dict[str, Any], report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "trackName": raw_data.get("trackName"),
        "trackConfig": raw_data.get("trackConfig"),
        "provider": raw_data.get("provider"),
        "source": raw_data.get("source"),
        "runtimeApplied": False,
        "note": "Offline cleanup preview only; active runtime geometry is unchanged.",
        "metadata": cleaned["metadata"],
        "qualitySummary": {
            "rawTotalPoints": report["totalPoints"],
            "rawSuspiciousSegmentCount": report["suspiciousSegmentCount"],
            "rawLocalWidthStats": report["localWidthStats"],
            "rawLoopClosure": report["loopClosure"],
        },
        "centerline": cleaned["centerline"],
        "leftEdge": cleaned["leftEdge"],
        "rightEdge": cleaned["rightEdge"],
        "localWidth": cleaned["localWidth"],
    }


def monotonic_audit(values: List[float], name: str) -> Dict[str, Any]:
    deltas = [
        {
            "index": index,
            "nextIndex": index + 1,
            "delta": round(float(values[index + 1]) - float(values[index]), 9),
            "from": round(float(values[index]), 9),
            "to": round(float(values[index + 1]), 9),
        }
        for index in range(len(values) - 1)
    ]
    negative = [item for item in deltas if item["delta"] < -1e-9]
    zero = [item for item in deltas if abs(item["delta"]) <= 1e-12]
    return {
        "name": name,
        "count": len(values),
        "first": round(values[0], 9) if values else None,
        "last": round(values[-1], 9) if values else None,
        "deltaStats": stats([item["delta"] for item in deltas]) if deltas else {},
        "negativeDeltaCount": len(negative),
        "zeroDeltaCount": len(zero),
        "negativeDeltas": negative[:50],
        "zeroDeltas": zero[:50],
    }


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    track = load_track_geometry(TRACK_CACHE)
    raw = {
        "centerline": track["centerline"],
        "leftEdge": track["leftEdge"],
        "rightEdge": track["rightEdge"],
        "localWidth": track["localWidth"],
    }
    report = audit_geometry(raw["centerline"], raw["leftEdge"], raw["rightEdge"], raw["localWidth"])
    cleaned = cleanup_geometry(raw["centerline"], raw["leftEdge"], raw["rightEdge"], raw["localWidth"])
    cleaned_report = audit_geometry(cleaned["centerline"], cleaned["leftEdge"], cleaned["rightEdge"], cleaned["localWidth"])
    report["trackName"] = track["raw"].get("trackName")
    report["trackConfig"] = track["raw"].get("trackConfig")
    report["provider"] = track["raw"].get("provider")
    report["source"] = track["raw"].get("source")
    report["cachePath"] = str(TRACK_CACHE)
    report["distanceAlongTrackAudit"] = monotonic_audit(track["distanceAlongTrack"], "distanceAlongTrack")
    report["pAudit"] = monotonic_audit(track["p"], "p")
    report["cleanedPreviewSummary"] = {
        "totalPoints": cleaned_report["totalPoints"],
        "suspiciousSegmentCount": cleaned_report["suspiciousSegmentCount"],
        "segmentLengthStats": cleaned_report["segmentLengthStats"],
        "localWidthStats": cleaned_report["localWidthStats"],
        "loopClosure": cleaned_report["loopClosure"],
    }

    quality_path = DEBUG_DIR / "track_geometry_quality_report.json"
    cleaned_json_path = DEBUG_DIR / "track_geometry_cleaned.json"
    cleaned_preview_path = DEBUG_DIR / "track_geometry_cleaned_preview.svg"
    raw_vs_cleaned_path = DEBUG_DIR / "track_geometry_raw_vs_cleaned.svg"
    problem_segments_path = DEBUG_DIR / "track_geometry_problem_segments.svg"

    quality_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    cleaned_json_path.write_text(json.dumps(cleaned_payload(track["raw"], cleaned, report), ensure_ascii=False, indent=2), encoding="utf-8")
    write_cleaned_preview_svg(cleaned, cleaned_preview_path)
    write_raw_vs_cleaned_svg(raw, cleaned, raw_vs_cleaned_path)
    write_problem_segments_svg(raw, report, problem_segments_path)

    print(json.dumps({
        "qualityReport": str(quality_path),
        "cleanedJson": str(cleaned_json_path),
        "cleanedPreview": str(cleaned_preview_path),
        "rawVsCleaned": str(raw_vs_cleaned_path),
        "problemSegments": str(problem_segments_path),
        "summary": {
            "rawTotalPoints": report["totalPoints"],
            "rawSuspiciousSegmentCount": report["suspiciousSegmentCount"],
            "rawSegmentStats": report["segmentLengthStats"]["centerline"],
            "rawWidthStats": report["localWidthStats"],
            "cleanedTotalPoints": cleaned_report["totalPoints"],
            "cleanedSegmentStats": cleaned_report["segmentLengthStats"]["centerline"],
            "cleanedWidthStats": cleaned_report["localWidthStats"],
        },
    }, indent=2))


if __name__ == "__main__":
    main()
