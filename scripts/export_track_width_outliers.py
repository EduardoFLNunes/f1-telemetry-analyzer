from pathlib import Path
import json
import math
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = REPO_ROOT / "data" / "debug"

DEFAULT_TRACK = "vhe_interlagos"
OUTLIER_COUNT = 50
SMALL_LOOP_AREA = 2500.0
SMALL_LOOP_PERIMETER = 250.0


def distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))


def round_point(point: Optional[Sequence[float]]) -> Optional[List[float]]:
    if point is None:
        return None
    return [round(float(point[0]), 6), round(float(point[1]), 6)]


def point_segment_distance(
    point: Sequence[float],
    start: Sequence[float],
    end: Sequence[float],
) -> Tuple[float, List[float], float]:
    px, py = float(point[0]), float(point[1])
    ax, ay = float(start[0]), float(start[1])
    bx, by = float(end[0]), float(end[1])
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        closest = [ax, ay]
        return distance(point, closest), closest, 0.0
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    closest = [ax + t * dx, ay + t * dy]
    return distance(point, closest), closest, t


def parse_used_loop_count(source: str) -> Optional[int]:
    match = re.match(r"clean_boundary_loops_top_(\d+)$", source or "")
    if match:
        return int(match.group(1))
    if source == "clean_boundary_loops_all":
        return None
    return None


def loop_segments(loop: Dict[str, Any]) -> List[Tuple[List[float], List[float], int]]:
    points = loop.get("points", [])
    return [
        (points[index], points[index + 1], index)
        for index in range(len(points) - 1)
    ]


def nearest_loop_source(
    point: Optional[Sequence[float]],
    loops: Sequence[Dict[str, Any]],
    used_loop_count: Optional[int],
) -> Optional[Dict[str, Any]]:
    if point is None:
        return None
    best: Optional[Dict[str, Any]] = None
    for loop in loops:
        for start, end, segment_index in loop_segments(loop):
            dist, closest, t = point_segment_distance(point, start, end)
            if best is None or dist < best["distanceToLoop"]:
                classification = loop.get("classification")
                loop_id = int(loop.get("loopId", -1))
                small = float(loop.get("area", 0.0)) < SMALL_LOOP_AREA or float(loop.get("perimeter", 0.0)) < SMALL_LOOP_PERIMETER
                auxiliary = used_loop_count is not None and loop_id >= used_loop_count
                best = {
                    "loopId": loop_id,
                    "sourceLoopId": loop.get("sourceLoopId"),
                    "classification": classification,
                    "segmentIndex": segment_index,
                    "distanceToLoop": round(dist, 6),
                    "closestPoint": round_point(closest),
                    "segmentT": round(float(t), 6),
                    "area": loop.get("area"),
                    "perimeter": loop.get("perimeter"),
                    "pointCount": loop.get("pointCount"),
                    "isSmallLoop": small,
                    "isInternalLoop": classification != "external",
                    "isAuxiliaryLoop": auxiliary,
                    "isSmallInternalOrAuxiliary": bool(small or classification != "external" or auxiliary),
                }
    return best


def bounds_from_points(points: Sequence[Sequence[float]]) -> Dict[str, float]:
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return {
        "minX": round(min(xs), 6),
        "maxX": round(max(xs), 6),
        "minY": round(min(ys), 6),
        "maxY": round(max(ys), 6),
        "width": round(max(xs) - min(xs), 6),
        "height": round(max(ys) - min(ys), 6),
    }


def build_width_outliers(edges: Dict[str, Any], limit: int = OUTLIER_COUNT, *, bottom: bool = False) -> Dict[str, Any]:
    samples = [
        sample
        for sample in edges.get("edges", {}).get("samples", [])
        if sample.get("localWidth") is not None
    ]
    samples.sort(key=lambda item: float(item["localWidth"]), reverse=not bottom)
    outlier_samples = samples[:limit]
    loops = edges.get("boundary", {}).get("cleanLoops", [])
    metrics = edges.get("metrics", {})
    used_loop_count = parse_used_loop_count(metrics.get("raycastBoundarySource"))
    sample_count = max(1, int(edges.get("edges", {}).get("sampleCount", len(samples))) - 1)
    selected_component_id = edges.get("components", {}).get("selectedComponentId")
    selected_component = None
    for component in edges.get("components", {}).get("items", []):
        if component.get("componentId") == selected_component_id:
            selected_component = component
            break

    rows = []
    for rank, sample in enumerate(outlier_samples, start=1):
        index = int(sample["index"])
        fast_lane = sample.get("fastLane")
        centerline = sample.get("centerline")
        left_source = nearest_loop_source(sample.get("leftEdge"), loops, used_loop_count)
        right_source = nearest_loop_source(sample.get("rightEdge"), loops, used_loop_count)
        either_special = bool(
            (left_source and left_source["isSmallInternalOrAuxiliary"])
            or (right_source and right_source["isSmallInternalOrAuxiliary"])
        )
        interval_internal_internal = sample.get("leftLoopType") == "internal_hole" and sample.get("rightLoopType") == "internal_hole"
        interval_contains_fast_lane = bool(sample.get("selectedIntervalContainsFastLane"))
        interval_midpoint_inside = bool(sample.get("midpointInsideSurface"))
        interval_internal_hole_jump = bool(
            interval_internal_internal
            and not (interval_contains_fast_lane and interval_midpoint_inside)
        )
        row = {
            "rank": rank,
            "index": index,
            "p": round(index / sample_count, 8),
            "local_width": round(float(sample["localWidth"]), 6),
            "centerline": round_point(centerline),
            "fast_lane": round_point(fast_lane),
            "left_edge": round_point(sample.get("leftEdge")),
            "right_edge": round_point(sample.get("rightEdge")),
            "tangent": round_point(sample.get("tangent")),
            "normal": round_point(sample.get("normal")),
            "edgeFromSmallInternalOrAuxiliaryLoop": either_special,
            "left_edge_source": left_source,
            "right_edge_source": right_source,
            "distance_fast_lane_to_centerline": round(distance(fast_lane, centerline), 6) if fast_lane and centerline else None,
            "lateral_reference_offset": sample.get("lateralReferenceOffset"),
            "valid": sample.get("valid"),
            "interpolated": sample.get("interpolated"),
            "invalidReason": sample.get("invalidReason"),
            "allIntersectionCount": sample.get("allIntersectionCount"),
            "selectedIntervalIndex": sample.get("selectedIntervalIndex"),
            "selectedIntervalWidth": sample.get("selectedIntervalWidth"),
            "selectedIntervalContainsFastLane": sample.get("selectedIntervalContainsFastLane"),
            "leftLoopType": sample.get("leftLoopType"),
            "rightLoopType": sample.get("rightLoopType"),
            "midpointInsideSurface": sample.get("midpointInsideSurface"),
            "fastLaneInsideSurface": sample.get("fastLaneInsideSurface"),
            "correctionReason": sample.get("correctionReason"),
            "intervalInternalHoleToInternalHole": interval_internal_internal,
            "intervalInternalHoleJump": interval_internal_hole_jump,
            "selectedInterval": sample.get("selectedInterval"),
            "surface_component": {
                "componentId": selected_component_id,
                "triangleCount": selected_component.get("triangleCount") if selected_component else None,
                "area": selected_component.get("area") if selected_component else None,
                "surfaceCounts": selected_component.get("surfaceCounts") if selected_component else None,
                "includedSurfaceKeys": edges.get("includedSurfaceKeys", []),
            },
        }
        rows.append(row)

    widths = [row["local_width"] for row in rows]
    contaminated = [
        row for row in rows
        if row["edgeFromSmallInternalOrAuxiliaryLoop"]
    ]
    return {
        "trackName": edges.get("trackName"),
        "trackConfig": edges.get("trackConfig"),
        "source": "track_edges_from_surface",
        "mode": "bottom_local_width" if bottom else "top_local_width",
        "goal": "Inspect bottom 50 narrowest local_width samples and identify extraction artifacts." if bottom else "Inspect top 50 widest local_width samples and identify auxiliary/internal loop influence.",
        "thresholds": {
            "smallLoopArea": SMALL_LOOP_AREA,
            "smallLoopPerimeter": SMALL_LOOP_PERIMETER,
            "usedLoopCount": used_loop_count,
            "raycastBoundarySource": metrics.get("raycastBoundarySource"),
        },
        "summary": {
            "sampleCount": len(rows),
            "maxLocalWidth": max(widths) if widths else None,
            "minOutlierLocalWidth": min(widths) if widths else None,
            "outliersWithSmallInternalOrAuxiliaryEdge": len(contaminated),
            "outliersWithAuxiliaryLoopEdge": sum(
                1 for row in rows
                if (row["left_edge_source"] and row["left_edge_source"]["isAuxiliaryLoop"])
                or (row["right_edge_source"] and row["right_edge_source"]["isAuxiliaryLoop"])
            ),
            "outliersWithSmallLoopEdge": sum(
                1 for row in rows
                if (row["left_edge_source"] and row["left_edge_source"]["isSmallLoop"])
                or (row["right_edge_source"] and row["right_edge_source"]["isSmallLoop"])
            ),
            "outliersWithInternalLoopEdge": sum(
                1 for row in rows
                if (row["left_edge_source"] and row["left_edge_source"]["isInternalLoop"])
                or (row["right_edge_source"] and row["right_edge_source"]["isInternalLoop"])
            ),
            "widthMetrics": metrics.get("width", {}),
            "selectedComponentId": selected_component_id,
            "intervalInternalHoleToInternalHole": sum(1 for row in rows if row.get("intervalInternalHoleToInternalHole")),
            "intervalInternalHoleJump": sum(1 for row in rows if row.get("intervalInternalHoleJump")),
            "selectedIntervalContainsFastLane": sum(1 for row in rows if row.get("selectedIntervalContainsFastLane")),
            "selectedIntervalMidpointInsideSurface": sum(1 for row in rows if row.get("midpointInsideSurface")),
            "correctedFromNearestInterval": sum(1 for row in rows if row.get("correctionReason") == "corrected_from_nearest_interval"),
        },
        "outliers": rows,
    }


def svg_polyline(points: Sequence[Sequence[float]], project, stroke: str, width: float, opacity: float = 1.0, dash: Optional[str] = None) -> str:
    if len(points) < 2:
        return ""
    point_text = " ".join(f"{project(point)[0]:.2f},{project(point)[1]:.2f}" for point in points)
    dash_text = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{point_text}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-opacity="{opacity}" stroke-linejoin="round" stroke-linecap="round"{dash_text}/>'


def build_outlier_svg(edges: Dict[str, Any], report: Dict[str, Any]) -> str:
    points = []
    for row in report["outliers"]:
        for key in ("left_edge", "right_edge", "centerline", "fast_lane"):
            if row.get(key):
                points.append(row[key])
    for series in ("centerline", "leftEdge", "rightEdge"):
        points.extend(edges.get("edges", {}).get(series, []))
    bounds = bounds_from_points(points)
    margin = 28
    width, height = 1200, 960
    scale = min(
        (width - margin * 2) / max(bounds["width"], 1.0),
        (height - margin * 2) / max(bounds["height"], 1.0),
    )

    def project(point: Sequence[float]) -> Tuple[float, float]:
        x = margin + (float(point[0]) - bounds["minX"]) * scale
        y = height - margin - (float(point[1]) - bounds["minY"]) * scale
        return x, y

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#080b10"/>',
        f'<text x="28" y="34" fill="#d9e6f2" font-family="Segoe UI, Arial" font-size="16">{"Bottom" if report.get("mode") == "bottom_local_width" else "Top"} {len(report["outliers"])} local_width samples - {report.get("trackName")}</text>',
        f'<text x="28" y="56" fill="#9fb0c4" font-family="Segoe UI, Arial" font-size="12">max={report["summary"].get("maxLocalWidth")}m; auxiliary-loop edges={report["summary"].get("outliersWithAuxiliaryLoopEdge")}; small-loop edges={report["summary"].get("outliersWithSmallLoopEdge")}</text>',
    ]
    for loop in edges.get("boundary", {}).get("cleanLoops", [])[:4]:
        stroke = "#27d8ff" if loop.get("classification") == "external" else "#d8dde7"
        opacity = 0.35 if loop.get("classification") == "external" else 0.22
        parts.append(svg_polyline(loop.get("points", []), project, stroke, 1.0, opacity))
    parts.append(svg_polyline(edges.get("edges", {}).get("leftEdge", []), project, "#4aa3ff", 1.4, 0.42))
    parts.append(svg_polyline(edges.get("edges", {}).get("rightEdge", []), project, "#ff637d", 1.4, 0.42))
    parts.append(svg_polyline(edges.get("edges", {}).get("centerline", []), project, "#5dff9a", 1.3, 0.55))

    for row in reversed(report["outliers"]):
        left = row["left_edge"]
        right = row["right_edge"]
        center = row["centerline"]
        fast = row["fast_lane"]
        contaminated = row["edgeFromSmallInternalOrAuxiliaryLoop"]
        color = "#40e0d0" if report.get("mode") == "bottom_local_width" and not contaminated else ("#ff4f8b" if contaminated else "#ffd166")
        lx, ly = project(left)
        rx, ry = project(right)
        cx, cy = project(center)
        fx, fy = project(fast)
        stroke_width = 2.1 if row["rank"] <= 10 else 1.2
        parts.append(f'<line x1="{lx:.2f}" y1="{ly:.2f}" x2="{rx:.2f}" y2="{ry:.2f}" stroke="{color}" stroke-width="{stroke_width}" stroke-opacity="0.72"/>')
        parts.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{3.2 if row["rank"] <= 10 else 2.2}" fill="#5dff9a" fill-opacity="0.9"/>')
        parts.append(f'<circle cx="{fx:.2f}" cy="{fy:.2f}" r="{2.6 if row["rank"] <= 10 else 1.8}" fill="#f4b350" fill-opacity="0.9"/>')
        if row["rank"] <= 12:
            parts.append(f'<text x="{cx + 5:.2f}" y="{cy - 5:.2f}" fill="#f8fbff" font-family="Segoe UI, Arial" font-size="10">{row["rank"]}: {row["local_width"]:.1f}m</text>')
    parts.append("</svg>")
    return "\n".join(part for part in parts if part)


def main() -> None:
    track = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TRACK
    edges_name = sys.argv[2] if len(sys.argv) > 2 else f"track_edges_from_surface_{track}.json"
    output_prefix = sys.argv[3] if len(sys.argv) > 3 else f"track_width_outliers_{track}"
    bottom = any(arg.lower() in {"--bottom", "bottom", "mode=bottom"} for arg in sys.argv[4:])
    edges_path = DEBUG_DIR / edges_name
    if not edges_path.exists():
        raise SystemExit(f"Missing input: {edges_path}")
    edges = json.loads(edges_path.read_text(encoding="utf-8"))
    report = build_width_outliers(edges, bottom=bottom)
    report["sourceFile"] = str(edges_path)
    json_path = DEBUG_DIR / f"{output_prefix}.json"
    svg_path = DEBUG_DIR / f"{output_prefix}.svg"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    svg_path.write_text(build_outlier_svg(edges, report), encoding="utf-8")
    print({"json": str(json_path), "svg": str(svg_path), "summary": report["summary"]})


if __name__ == "__main__":
    main()
