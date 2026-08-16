import json
import logging
import math
import struct
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from scipy.spatial import KDTree

from ..geometry.marking_classification import classify_marking_rings
from .track_surface_polygon import build_track_surface_polygon_from_manifest

logger = logging.getLogger(__name__)


COMPONENT_PRECISION = 1
BOUNDARY_PRECISION = 2
MIN_LOOP_AREA = 40.0
MIN_LOOP_PERIMETER = 20.0
SIMPLIFY_TOLERANCE = 0.35
MIN_TRACK_WIDTH = 4.0
MAX_TRACK_WIDTH = 85.0
MAX_RAY_SIDE_DISTANCE = 90.0
MAX_INTERVAL_TRACK_WIDTH = 35.0
MAX_INTERVAL_RAY_DISTANCE = 140.0
SURFACE_GRID_CELL_SIZE = 30.0


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))


def _round_point(point: Sequence[float], digits: int = 6) -> List[float]:
    return [round(float(point[0]), digits), round(float(point[1]), digits)]


def _quantized(point: Sequence[float], precision: int) -> Tuple[int, int]:
    scale = 10**precision
    return int(round(float(point[0]) * scale)), int(round(float(point[1]) * scale))


def _bounds2() -> Tuple[List[float], List[float]]:
    return [float("inf"), float("inf")], [float("-inf"), float("-inf")]


def _update_bounds(bounds_min: List[float], bounds_max: List[float], point: Sequence[float]) -> None:
    bounds_min[0] = min(bounds_min[0], float(point[0]))
    bounds_min[1] = min(bounds_min[1], float(point[1]))
    bounds_max[0] = max(bounds_max[0], float(point[0]))
    bounds_max[1] = max(bounds_max[1], float(point[1]))


def _bounds_payload(bounds_min: Sequence[float], bounds_max: Sequence[float]) -> Dict[str, float]:
    return {
        "minX": round(float(bounds_min[0]), 6),
        "maxX": round(float(bounds_max[0]), 6),
        "minY": round(float(bounds_min[1]), 6),
        "maxY": round(float(bounds_max[1]), 6),
        "width": round(float(bounds_max[0]) - float(bounds_min[0]), 6),
        "height": round(float(bounds_max[1]) - float(bounds_min[1]), 6),
    }


def _signed_area(points: Sequence[Sequence[float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    end = len(points) - 1 if points[0] == points[-1] else len(points)
    for index in range(end):
        a = points[index]
        b = points[(index + 1) % end]
        area += float(a[0]) * float(b[1]) - float(b[0]) * float(a[1])
    return area * 0.5


def _perimeter(points: Sequence[Sequence[float]]) -> float:
    if len(points) < 2:
        return 0.0
    return sum(_distance(points[index], points[index + 1]) for index in range(len(points) - 1))


def _triangle_centroid(points: Sequence[Sequence[float]]) -> Tuple[float, float]:
    return (
        (float(points[0][0]) + float(points[1][0]) + float(points[2][0])) / 3.0,
        (float(points[0][1]) + float(points[1][1]) + float(points[2][1])) / 3.0,
    )


def _cross_2d(a: Sequence[float], b: Sequence[float]) -> float:
    return float(a[0]) * float(b[1]) - float(a[1]) * float(b[0])


def _point_in_triangle(point: Sequence[float], triangle: Sequence[Sequence[float]]) -> bool:
    px, py = float(point[0]), float(point[1])
    ax, ay = float(triangle[0][0]), float(triangle[0][1])
    bx, by = float(triangle[1][0]), float(triangle[1][1])
    cx, cy = float(triangle[2][0]), float(triangle[2][1])
    denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(denominator) <= 1e-12:
        return False
    alpha = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denominator
    beta = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denominator
    gamma = 1.0 - alpha - beta
    return alpha >= -1e-7 and beta >= -1e-7 and gamma >= -1e-7


class _TriangleSurfaceIndex:
    def __init__(
        self,
        triangles: Sequence[Dict[str, Any]],
        triangle_indices: Sequence[int],
        *,
        cell_size: float = SURFACE_GRID_CELL_SIZE,
    ):
        self.cell_size = float(cell_size)
        self.grid: Dict[Tuple[int, int], List[Sequence[Sequence[float]]]] = defaultdict(list)
        for triangle_index in triangle_indices:
            points = triangles[triangle_index]["vertices"]
            xs = [float(point[0]) for point in points]
            ys = [float(point[1]) for point in points]
            min_cell_x = math.floor(min(xs) / self.cell_size)
            max_cell_x = math.floor(max(xs) / self.cell_size)
            min_cell_y = math.floor(min(ys) / self.cell_size)
            max_cell_y = math.floor(max(ys) / self.cell_size)
            for cell_x in range(min_cell_x, max_cell_x + 1):
                for cell_y in range(min_cell_y, max_cell_y + 1):
                    self.grid[(cell_x, cell_y)].append(points)

    def contains(self, point: Sequence[float]) -> bool:
        cell = (math.floor(float(point[0]) / self.cell_size), math.floor(float(point[1]) / self.cell_size))
        for triangle in self.grid.get(cell, []):
            if _point_in_triangle(point, triangle):
                return True
        return False


def _point_line_distance(point: Sequence[float], start: Sequence[float], end: Sequence[float]) -> float:
    px, py = float(point[0]), float(point[1])
    ax, ay = float(start[0]), float(start[1])
    bx, by = float(end[0]), float(end[1])
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def _rdp(points: Sequence[Sequence[float]], tolerance: float) -> List[List[float]]:
    if len(points) <= 2:
        return [_round_point(point) for point in points]
    start, end = points[0], points[-1]
    max_distance = -1.0
    max_index = 0
    for index in range(1, len(points) - 1):
        distance = _point_line_distance(points[index], start, end)
        if distance > max_distance:
            max_distance = distance
            max_index = index
    if max_distance > tolerance:
        left = _rdp(points[: max_index + 1], tolerance)
        right = _rdp(points[max_index:], tolerance)
        return left[:-1] + right
    return [_round_point(start), _round_point(end)]


def _simplify_closed_loop(points: Sequence[Sequence[float]], tolerance: float) -> List[List[float]]:
    if len(points) < 4:
        return [_round_point(point) for point in points]
    raw = list(points[:-1] if points[0] == points[-1] else points)
    if len(raw) < 3:
        return [_round_point(point) for point in points]
    anchor_index = min(range(len(raw)), key=lambda index: (raw[index][0], raw[index][1]))
    rotated = raw[anchor_index:] + raw[:anchor_index] + [raw[anchor_index]]
    simplified = _rdp(rotated, tolerance)
    if simplified[0] != simplified[-1]:
        simplified.append(simplified[0])
    return simplified


class _UnionFind:
    def __init__(self) -> None:
        self.parent: Dict[Tuple[int, int], Tuple[int, int]] = {}

    def find(self, item: Tuple[int, int]) -> Tuple[int, int]:
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: Tuple[int, int], b: Tuple[int, int]) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self.parent[root_b] = root_a


def _component_analysis(triangles: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[int, int]]:
    uf = _UnionFind()
    triangle_keys: List[List[Tuple[int, int]]] = []
    for triangle in triangles:
        keys = [_quantized(point, COMPONENT_PRECISION) for point in triangle["vertices"]]
        triangle_keys.append(keys)
        uf.union(keys[0], keys[1])
        uf.union(keys[0], keys[2])

    root_to_indices: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for index, keys in enumerate(triangle_keys):
        root_to_indices[uf.find(keys[0])].append(index)

    roots = sorted(
        root_to_indices,
        key=lambda root: (
            -sum(float(triangles[index].get("area", 0.0)) for index in root_to_indices[root]),
            -len(root_to_indices[root]),
        ),
    )
    triangle_to_component: Dict[int, int] = {}
    components: List[Dict[str, Any]] = []
    for component_id, root in enumerate(roots):
        indices = root_to_indices[root]
        bounds_min, bounds_max = _bounds2()
        area = 0.0
        weighted_x = 0.0
        weighted_y = 0.0
        mesh_counts: Counter[str] = Counter()
        surface_counts: Counter[str] = Counter()
        edge_counts: Dict[Tuple[Tuple[int, int], Tuple[int, int]], int] = defaultdict(int)
        edge_lengths: Dict[Tuple[Tuple[int, int], Tuple[int, int]], float] = {}
        for triangle_index in indices:
            triangle_to_component[triangle_index] = component_id
            triangle = triangles[triangle_index]
            points = triangle["vertices"]
            tri_area = float(triangle.get("area", 0.0))
            area += tri_area
            cx, cy = _triangle_centroid(points)
            weighted_x += cx * tri_area
            weighted_y += cy * tri_area
            mesh_counts[str(triangle.get("mesh", "unknown"))] += 1
            surface_counts[str(triangle.get("surface", "unknown"))] += 1
            for point in points:
                _update_bounds(bounds_min, bounds_max, point)
            for start, end in ((points[0], points[1]), (points[1], points[2]), (points[2], points[0])):
                qa, qb = _quantized(start, BOUNDARY_PRECISION), _quantized(end, BOUNDARY_PRECISION)
                key = tuple(sorted((qa, qb)))
                edge_counts[key] += 1
                edge_lengths[key] = _distance(start, end)
        perimeter = sum(length for key, length in edge_lengths.items() if edge_counts[key] == 1)
        centroid = [weighted_x / area, weighted_y / area] if area > 1e-9 else [0.0, 0.0]
        components.append(
            {
                "componentId": component_id,
                "triangleCount": len(indices),
                "area": round(area, 6),
                "perimeterEstimate": round(perimeter, 6),
                "centroid": _round_point(centroid),
                "bbox": _bounds_payload(bounds_min, bounds_max),
                "meshCounts": dict(mesh_counts.most_common()),
                "surfaceCounts": dict(surface_counts.most_common()),
                "selected": component_id == 0,
            }
        )
    return components, triangle_to_component


def _selected_triangle_indices(triangle_to_component: Dict[int, int], selected_component_id: int) -> List[int]:
    return [index for index, component_id in triangle_to_component.items() if component_id == selected_component_id]


def _boundary_edges(
    triangles: Sequence[Dict[str, Any]],
    triangle_indices: Iterable[int],
    *,
    precision: int = BOUNDARY_PRECISION,
) -> Tuple[List[Dict[str, Any]], Dict[Tuple[int, int], List[float]]]:
    edge_counts: Dict[Tuple[Tuple[int, int], Tuple[int, int]], int] = defaultdict(int)
    edge_points: Dict[Tuple[Tuple[int, int], Tuple[int, int]], Tuple[List[float], List[float]]] = {}
    node_accumulator: Dict[Tuple[int, int], List[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])

    for triangle_index in triangle_indices:
        points = triangles[triangle_index]["vertices"]
        for point in points:
            key = _quantized(point, precision)
            node_accumulator[key][0] += float(point[0])
            node_accumulator[key][1] += float(point[1])
            node_accumulator[key][2] += 1.0
        for start, end in ((points[0], points[1]), (points[1], points[2]), (points[2], points[0])):
            qa, qb = _quantized(start, precision), _quantized(end, precision)
            key = tuple(sorted((qa, qb)))
            edge_counts[key] += 1
            edge_points[key] = (_round_point(start), _round_point(end))

    node_points = {
        key: [value[0] / value[2], value[1] / value[2]]
        for key, value in node_accumulator.items()
        if value[2] > 0
    }
    boundary = []
    for edge_id, (key, count) in enumerate(edge_counts.items()):
        if count != 1:
            continue
        a, b = key
        pa, pb = edge_points[key]
        boundary.append(
            {
                "edgeId": edge_id,
                "keys": [a, b],
                "from": pa,
                "to": pb,
                "length": round(_distance(pa, pb), 6),
            }
        )
    return boundary, node_points


def _choose_next_edge(
    previous_key: Tuple[int, int],
    current_key: Tuple[int, int],
    candidate_edges: Sequence[int],
    edges: Sequence[Dict[str, Any]],
    node_points: Dict[Tuple[int, int], List[float]],
    start_key: Tuple[int, int],
    path_length: int,
) -> Tuple[int, Tuple[int, int]]:
    if path_length > 2:
        for edge_index in candidate_edges:
            a, b = edges[edge_index]["keys"]
            next_key = b if a == current_key else a
            if next_key == start_key:
                return edge_index, next_key

    prev_point = node_points.get(previous_key, [previous_key[0], previous_key[1]])
    current_point = node_points.get(current_key, [current_key[0], current_key[1]])
    incoming = [current_point[0] - prev_point[0], current_point[1] - prev_point[1]]
    incoming_len = math.hypot(incoming[0], incoming[1]) or 1.0

    best: Optional[Tuple[float, int, Tuple[int, int]]] = None
    for edge_index in candidate_edges:
        a, b = edges[edge_index]["keys"]
        next_key = b if a == current_key else a
        if next_key == previous_key and len(candidate_edges) > 1:
            continue
        next_point = node_points.get(next_key, [next_key[0], next_key[1]])
        outgoing = [next_point[0] - current_point[0], next_point[1] - current_point[1]]
        outgoing_len = math.hypot(outgoing[0], outgoing[1]) or 1.0
        dot = max(-1.0, min(1.0, (incoming[0] * outgoing[0] + incoming[1] * outgoing[1]) / (incoming_len * outgoing_len)))
        turn = math.acos(dot)
        candidate = (turn, edge_index, next_key)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        edge_index = candidate_edges[0]
        a, b = edges[edge_index]["keys"]
        return edge_index, b if a == current_key else a
    return best[1], best[2]


def _build_boundary_loops(
    boundary_edges: Sequence[Dict[str, Any]],
    node_points: Dict[Tuple[int, int], List[float]],
    min_area: float = MIN_LOOP_AREA,
    min_perimeter: float = MIN_LOOP_PERIMETER,
    simplify_tolerance: float = SIMPLIFY_TOLERANCE,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    adjacency: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    normalized_edges: List[Dict[str, Any]] = []
    for edge_index, edge in enumerate(boundary_edges):
        a_raw, b_raw = edge["keys"]
        a = tuple(a_raw)
        b = tuple(b_raw)
        normalized_edges.append({"keys": [a, b], "from": edge["from"], "to": edge["to"]})
        adjacency[a].append(edge_index)
        adjacency[b].append(edge_index)

    visited = set()
    raw_loops: List[Dict[str, Any]] = []
    for edge_index, edge in enumerate(normalized_edges):
        if edge_index in visited:
            continue
        start_key, current_key = edge["keys"]
        previous_key = start_key
        path_keys = [start_key, current_key]
        visited.add(edge_index)
        closed = False
        for _ in range(len(normalized_edges) + 5):
            if current_key == start_key and len(path_keys) > 2:
                closed = True
                break
            candidates = [candidate for candidate in adjacency[current_key] if candidate not in visited]
            if not candidates:
                break
            next_edge, next_key = _choose_next_edge(
                previous_key,
                current_key,
                candidates,
                normalized_edges,
                node_points,
                start_key,
                len(path_keys),
            )
            visited.add(next_edge)
            previous_key, current_key = current_key, next_key
            path_keys.append(current_key)
            if current_key == start_key and len(path_keys) > 2:
                closed = True
                break

        points = [_round_point(node_points.get(key, [key[0], key[1]])) for key in path_keys]
        if closed and points[0] != points[-1]:
            points.append(points[0])
        signed_area = _signed_area(points) if closed else 0.0
        perimeter = _perimeter(points)
        raw_loops.append(
            {
                "loopId": len(raw_loops),
                "closed": closed,
                "pointCount": len(points),
                "area": round(abs(signed_area), 6),
                "signedArea": round(signed_area, 6),
                "perimeter": round(perimeter, 6),
                "points": points,
            }
        )

    significant = [
        loop
        for loop in raw_loops
        if loop["closed"] and loop["area"] >= min_area and loop["perimeter"] >= min_perimeter
    ]
    significant.sort(key=lambda loop: (loop["area"], loop["perimeter"]), reverse=True)
    clean_loops: List[Dict[str, Any]] = []
    for index, loop in enumerate(significant):
        simplified = _simplify_closed_loop(loop["points"], simplify_tolerance)
        area = abs(_signed_area(simplified))
        perimeter = _perimeter(simplified)
        clean_loops.append(
            {
                "loopId": index,
                "sourceLoopId": loop["loopId"],
                "classification": "external" if index == 0 else "internal_hole",
                "closed": True,
                "pointCount": len(simplified),
                "rawPointCount": loop["pointCount"],
                "area": round(area, 6),
                "perimeter": round(perimeter, 6),
                "points": simplified,
            }
        )
    return raw_loops, clean_loops


def parse_fast_lane_ai(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {"path": None, "version": None, "pointCount": 0, "points": [], "diagnostics": [{"code": "missing_fast_lane", "message": "No fast_lane.ai path resolved"}]}
    ai_path = Path(path)
    if not ai_path.exists():
        return {"path": str(ai_path), "version": None, "pointCount": 0, "points": [], "diagnostics": [{"code": "missing_fast_lane", "message": "fast_lane.ai file is missing"}]}
    data = ai_path.read_bytes()
    diagnostics: List[Dict[str, Any]] = []
    if len(data) < 16:
        return {"path": str(ai_path), "version": None, "pointCount": 0, "points": [], "diagnostics": [{"code": "invalid_fast_lane", "message": "fast_lane.ai is too small"}]}
    version, point_count = struct.unpack_from("<II", data, 0)
    offset = 16
    stride = 20
    expected = offset + point_count * stride
    if expected > len(data):
        diagnostics.append({"code": "fast_lane_truncated", "message": "fast_lane.ai ended before declared point count", "declaredPointCount": point_count})
        point_count = max(0, (len(data) - offset) // stride)
    points = []
    for index in range(point_count):
        point_offset = offset + index * stride
        world_x, world_y, world_z = struct.unpack_from("<3f", data, point_offset)
        distance = struct.unpack_from("<f", data, point_offset + 12)[0]
        raw_index = struct.unpack_from("<I", data, point_offset + 16)[0]
        points.append(
            {
                "index": index,
                "worldPosition": [round(float(world_x), 6), round(float(world_y), 6), round(float(world_z), 6)],
                "mapPosition": [round(float(world_x), 6), round(float(-world_z), 6)],
                "distance": round(float(distance), 6),
                "rawIndex": int(raw_index),
            }
        )
    return {"path": str(ai_path), "version": int(version), "pointCount": len(points), "points": points, "diagnostics": diagnostics}


def _segments_from_loops(loops: Sequence[Dict[str, Any]], limit: Optional[int] = None) -> List[Tuple[List[float], List[float]]]:
    selected = loops[:limit] if limit else loops
    segments = []
    for loop in selected:
        points = loop.get("points", [])
        for index in range(len(points) - 1):
            segments.append((_round_point(points[index]), _round_point(points[index + 1])))
    return segments


def _segments_from_loops_with_metadata(
    loops: Sequence[Dict[str, Any]],
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    selected = loops[:limit] if limit else loops
    segments: List[Dict[str, Any]] = []
    for loop in selected:
        points = loop.get("points", [])
        for index in range(len(points) - 1):
            segments.append(
                {
                    "from": _round_point(points[index]),
                    "to": _round_point(points[index + 1]),
                    "loopId": loop.get("loopId"),
                    "sourceLoopId": loop.get("sourceLoopId"),
                    "loopType": loop.get("classification"),
                    "loopArea": loop.get("area"),
                    "loopPerimeter": loop.get("perimeter"),
                    "segmentIndex": index,
                }
            )
    return segments


def _segments_from_boundary(boundary_edges: Sequence[Dict[str, Any]]) -> List[Tuple[List[float], List[float]]]:
    return [(_round_point(edge["from"]), _round_point(edge["to"])) for edge in boundary_edges]


def _fast_lane_tangent(points: Sequence[Dict[str, Any]], index: int) -> Tuple[float, float]:
    count = len(points)
    prev_point = points[(index - 1) % count]["mapPosition"]
    next_point = points[(index + 1) % count]["mapPosition"]
    dx = float(next_point[0]) - float(prev_point[0])
    dy = float(next_point[1]) - float(prev_point[1])
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return 1.0, 0.0
    return dx / length, dy / length


def _raycast_sample(
    point: Sequence[float],
    normal: Sequence[float],
    segment_starts: np.ndarray,
    segment_vectors: np.ndarray,
) -> Tuple[Optional[float], Optional[float]]:
    if len(segment_starts) == 0:
        return None, None
    px, py = float(point[0]), float(point[1])
    rx, ry = float(normal[0]), float(normal[1])
    qpx = segment_starts[:, 0] - px
    qpy = segment_starts[:, 1] - py
    sx = segment_vectors[:, 0]
    sy = segment_vectors[:, 1]
    rxs = rx * sy - ry * sx
    mask = np.abs(rxs) > 1e-9
    if not np.any(mask):
        return None, None
    t = (qpx * sy - qpy * sx) / rxs
    u = (qpx * ry - qpy * rx) / rxs
    mask = mask & (u >= -1e-7) & (u <= 1.0000001) & (np.abs(t) > 0.25) & (np.abs(t) <= MAX_RAY_SIDE_DISTANCE)
    if not np.any(mask):
        return None, None
    hits = t[mask]
    positive = hits[hits > 0.0]
    negative = hits[hits < 0.0]
    left_t = float(np.min(positive)) if len(positive) else None
    right_t = float(np.max(negative)) if len(negative) else None
    return left_t, right_t


def _merge_intersections(intersections: Sequence[Dict[str, Any]], tolerance: float = 1e-5) -> List[Dict[str, Any]]:
    if not intersections:
        return []
    ordered = sorted(intersections, key=lambda item: item["t"])
    merged: List[Dict[str, Any]] = []
    for item in ordered:
        if merged and abs(float(item["t"]) - float(merged[-1]["t"])) <= tolerance:
            # Vertex hits often arrive twice from adjacent segments; keep one
            # crossing parameter while preserving a hint that it was merged.
            merged[-1]["mergedHitCount"] = int(merged[-1].get("mergedHitCount", 1)) + 1
            continue
        merged.append({**item, "mergedHitCount": 1})
    return merged


def _line_intersections_with_loop_segments(
    point: Sequence[float],
    normal: Sequence[float],
    loop_segments: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    px, py = float(point[0]), float(point[1])
    rx, ry = float(normal[0]), float(normal[1])
    intersections: List[Dict[str, Any]] = []
    for segment in loop_segments:
        start = segment["from"]
        end = segment["to"]
        qx, qy = float(start[0]), float(start[1])
        sx, sy = float(end[0]) - qx, float(end[1]) - qy
        denominator = _cross_2d([rx, ry], [sx, sy])
        if abs(denominator) <= 1e-9:
            continue
        q_minus_p = [qx - px, qy - py]
        t = _cross_2d(q_minus_p, [sx, sy]) / denominator
        u = _cross_2d(q_minus_p, [rx, ry]) / denominator
        if u < -1e-7 or u > 1.0000001 or abs(t) > MAX_INTERVAL_RAY_DISTANCE:
            continue
        hit = [px + rx * t, py + ry * t]
        intersections.append(
            {
                "t": float(t),
                "point": _round_point(hit),
                "loopId": segment.get("loopId"),
                "sourceLoopId": segment.get("sourceLoopId"),
                "loopType": segment.get("loopType"),
                "loopArea": segment.get("loopArea"),
                "loopPerimeter": segment.get("loopPerimeter"),
                "segmentIndex": segment.get("segmentIndex"),
            }
        )
    return _merge_intersections(intersections)


def _build_inside_intervals(
    point: Sequence[float],
    normal: Sequence[float],
    intersections: Sequence[Dict[str, Any]],
    surface_index: _TriangleSurfaceIndex,
) -> List[Dict[str, Any]]:
    intervals: List[Dict[str, Any]] = []
    if len(intersections) < 2:
        return intervals
    px, py = float(point[0]), float(point[1])
    nx, ny = float(normal[0]), float(normal[1])
    for index in range(len(intersections) - 1):
        start = intersections[index]
        end = intersections[index + 1]
        start_t = float(start["t"])
        end_t = float(end["t"])
        width = end_t - start_t
        if width <= 0.25:
            continue
        midpoint_t = (start_t + end_t) * 0.5
        midpoint = [px + nx * midpoint_t, py + ny * midpoint_t]
        midpoint_inside = surface_index.contains(midpoint)
        contains_fast_lane = start_t <= 0.0 <= end_t
        intervals.append(
            {
                "intervalIndex": index,
                "startT": start_t,
                "endT": end_t,
                "width": width,
                "midpoint": _round_point(midpoint),
                "midpointInsideSurface": midpoint_inside,
                "containsFastLane": contains_fast_lane,
                "rightHit": start,
                "leftHit": end,
                "plausibleWidth": MIN_TRACK_WIDTH <= width <= MAX_INTERVAL_TRACK_WIDTH,
            }
        )
    return intervals


def _select_inside_interval(intervals: Sequence[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    inside_plausible = [
        interval for interval in intervals
        if interval["midpointInsideSurface"] and interval["plausibleWidth"]
    ]
    containing = [interval for interval in inside_plausible if interval["containsFastLane"]]
    if containing:
        return min(containing, key=lambda interval: interval["width"]), None
    if inside_plausible:
        nearest = min(
            inside_plausible,
            key=lambda interval: min(abs(float(interval["startT"])), abs(float(interval["endT"]))),
        )
        return nearest, "corrected_from_nearest_interval"
    inside_too_wide = [
        interval for interval in intervals
        if interval["midpointInsideSurface"] and not interval["plausibleWidth"]
    ]
    if inside_too_wide:
        return None, "inside_intervals_implausible_width"
    return None, "no_inside_surface_interval"


def _run_interval_raycast(
    fast_lane: Dict[str, Any],
    loops: Sequence[Dict[str, Any]],
    surface_index: _TriangleSurfaceIndex,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    points = fast_lane.get("points", [])
    loop_segments = _segments_from_loops_with_metadata(loops)
    if not points or not loop_segments:
        return [], {"valid": 0, "invalid": len(points), "reason": "missing_fast_lane_or_boundary_loops"}

    samples: List[Dict[str, Any]] = []
    for index, fast_point in enumerate(points):
        map_position = fast_point["mapPosition"]
        tx, ty = _fast_lane_tangent(points, index)
        normal = [-ty, tx]
        fast_inside = surface_index.contains(map_position)
        intersections = _line_intersections_with_loop_segments(map_position, normal, loop_segments)
        intervals = _build_inside_intervals(map_position, normal, intersections, surface_index)
        selected_interval, correction_reason = _select_inside_interval(intervals)

        valid = selected_interval is not None
        left_edge = right_edge = centerline = None
        local_width = None
        offset = None
        invalid_reason = None if valid else correction_reason
        selected_contains_fast_lane = False
        midpoint_inside_surface = False
        left_loop_type = None
        right_loop_type = None
        selected_interval_index = None

        if selected_interval:
            left_t = float(selected_interval["endT"])
            right_t = float(selected_interval["startT"])
            left_edge = [
                float(map_position[0]) + float(normal[0]) * left_t,
                float(map_position[1]) + float(normal[1]) * left_t,
            ]
            right_edge = [
                float(map_position[0]) + float(normal[0]) * right_t,
                float(map_position[1]) + float(normal[1]) * right_t,
            ]
            centerline = [(left_edge[0] + right_edge[0]) * 0.5, (left_edge[1] + right_edge[1]) * 0.5]
            local_width = float(selected_interval["width"])
            offset = (float(map_position[0]) - centerline[0]) * normal[0] + (float(map_position[1]) - centerline[1]) * normal[1]
            selected_contains_fast_lane = bool(selected_interval["containsFastLane"])
            midpoint_inside_surface = bool(selected_interval["midpointInsideSurface"])
            left_loop_type = selected_interval["leftHit"].get("loopType")
            right_loop_type = selected_interval["rightHit"].get("loopType")
            selected_interval_index = selected_interval["intervalIndex"]

        samples.append(
            {
                "index": index,
                "fastLane": _round_point(map_position),
                # The map projection is flat, so the height would end here. It
                # rides alongside rather than inside the projection, which
                # everything downstream reads as two dimensional.
                "elevation": round(float(fast_point["worldPosition"][1]), 4),
                "tangent": _round_point([tx, ty]),
                "normal": _round_point(normal),
                "leftEdge": _round_point(left_edge) if left_edge else None,
                "rightEdge": _round_point(right_edge) if right_edge else None,
                "centerline": _round_point(centerline) if centerline else None,
                "localWidth": round(local_width, 6) if local_width is not None and valid else None,
                "lateralReferenceOffset": round(float(offset), 6) if offset is not None and valid else None,
                "valid": bool(valid),
                "interpolated": False,
                "invalidReason": invalid_reason,
                "allIntersectionCount": len(intersections),
                "selectedIntervalIndex": selected_interval_index,
                "selectedIntervalWidth": round(local_width, 6) if local_width is not None else None,
                "selectedIntervalContainsFastLane": selected_contains_fast_lane,
                "leftLoopType": left_loop_type,
                "rightLoopType": right_loop_type,
                "midpointInsideSurface": midpoint_inside_surface,
                "fastLaneInsideSurface": bool(fast_inside),
                "correctionReason": correction_reason,
                "selectedInterval": {
                    "startT": round(float(selected_interval["startT"]), 6),
                    "endT": round(float(selected_interval["endT"]), 6),
                    "midpoint": selected_interval["midpoint"],
                    "rightHit": selected_interval["rightHit"],
                    "leftHit": selected_interval["leftHit"],
                }
                if selected_interval
                else None,
            }
        )
    metrics = {"valid": sum(1 for sample in samples if sample["valid"]), "invalid": sum(1 for sample in samples if not sample["valid"])}
    return samples, metrics


MAX_FALLBACK_EDGE_JUMP = 4.0


def _reject_discontinuous_fallback_samples(
    samples: List[Dict[str, Any]],
    max_jump: float = MAX_FALLBACK_EDGE_JUMP,
) -> int:
    """Drop fallback samples that jumped onto a different strip of asphalt.

    When no plausible inside interval contains the racing line, the selection
    falls back to the interval nearest the ray origin. Around run-off and
    service asphalt that nearest interval can belong to a *different* strip, so
    the edge leaps sideways and back within a couple of samples -- the boxy
    excursions seen when overlaying the extraction on the KN5 surface. A track
    edge is continuous, so a fallback that cannot be reconciled with its
    neighbours is discarded and left for interpolation, which reconstructs it
    from the samples on either side.
    """
    rejected = 0
    for index, sample in enumerate(samples):
        if not sample.get("valid") or sample.get("correctionReason") != "corrected_from_nearest_interval":
            continue

        neighbour = None
        for offset in range(1, 6):
            previous = samples[index - offset] if index - offset >= 0 else None
            if previous and previous.get("valid") and previous.get("correctionReason") != "corrected_from_nearest_interval":
                neighbour = previous
                break
        if neighbour is None:
            continue

        jumped = False
        for key in ("leftEdge", "rightEdge"):
            current_edge = sample.get(key)
            neighbour_edge = neighbour.get(key)
            if current_edge and neighbour_edge and _distance(current_edge, neighbour_edge) > max_jump:
                jumped = True
                break
        if not jumped:
            continue

        sample.update(
            {
                "valid": False,
                "leftEdge": None,
                "rightEdge": None,
                "centerline": None,
                "localWidth": None,
                "lateralReferenceOffset": None,
                "invalidReason": "discontinuous_fallback_interval",
            }
        )
        rejected += 1
    return rejected


def _run_raycast(
    fast_lane: Dict[str, Any],
    segments: Sequence[Tuple[List[float], List[float]]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    points = fast_lane.get("points", [])
    if not points or not segments:
        return [], {"valid": 0, "invalid": len(points), "reason": "missing_fast_lane_or_segments"}

    starts = np.array([segment[0] for segment in segments], dtype=float)
    ends = np.array([segment[1] for segment in segments], dtype=float)
    vectors = ends - starts
    samples: List[Dict[str, Any]] = []
    for index, fast_point in enumerate(points):
        map_position = fast_point["mapPosition"]
        tx, ty = _fast_lane_tangent(points, index)
        normal = [-ty, tx]
        left_t, right_t = _raycast_sample(map_position, normal, starts, vectors)
        reason = None
        valid = left_t is not None and right_t is not None
        local_width = None
        left_edge = None
        right_edge = None
        centerline = None
        offset = None
        if valid:
            local_width = left_t - right_t
            if local_width < MIN_TRACK_WIDTH or local_width > MAX_TRACK_WIDTH:
                valid = False
                reason = "implausible_width"
            else:
                left_edge = [float(map_position[0]) + normal[0] * left_t, float(map_position[1]) + normal[1] * left_t]
                right_edge = [float(map_position[0]) + normal[0] * right_t, float(map_position[1]) + normal[1] * right_t]
                centerline = [(left_edge[0] + right_edge[0]) * 0.5, (left_edge[1] + right_edge[1]) * 0.5]
                offset = (float(map_position[0]) - centerline[0]) * normal[0] + (float(map_position[1]) - centerline[1]) * normal[1]
        elif left_t is None and right_t is None:
            reason = "no_hits"
        elif left_t is None:
            reason = "missing_left_hit"
        else:
            reason = "missing_right_hit"

        samples.append(
            {
                "index": index,
                "fastLane": _round_point(map_position),
                "tangent": _round_point([tx, ty]),
                "normal": _round_point(normal),
                "leftEdge": _round_point(left_edge) if left_edge else None,
                "rightEdge": _round_point(right_edge) if right_edge else None,
                "centerline": _round_point(centerline) if centerline else None,
                "localWidth": round(float(local_width), 6) if local_width is not None and valid else None,
                "lateralReferenceOffset": round(float(offset), 6) if offset is not None and valid else None,
                "valid": bool(valid),
                "interpolated": False,
                "invalidReason": None if valid else reason,
            }
        )
    metrics = {"valid": sum(1 for sample in samples if sample["valid"]), "invalid": sum(1 for sample in samples if not sample["valid"])}
    return samples, metrics


def _interpolate_samples(samples: List[Dict[str, Any]]) -> int:
    valid_indices = [index for index, sample in enumerate(samples) if sample["valid"]]
    if not valid_indices:
        return 0
    count = len(samples)
    interpolated = 0
    fields = ("leftEdge", "rightEdge", "centerline")
    for index, sample in enumerate(samples):
        if sample["valid"]:
            continue
        prev_candidates = [valid for valid in valid_indices if valid < index]
        next_candidates = [valid for valid in valid_indices if valid > index]
        prev_index = prev_candidates[-1] if prev_candidates else valid_indices[-1] - count
        next_index = next_candidates[0] if next_candidates else valid_indices[0] + count
        span = next_index - prev_index
        if span <= 0:
            continue
        alpha = (index - prev_index) / span
        prev_sample = samples[prev_index % count]
        next_sample = samples[next_index % count]
        for field in fields:
            a = prev_sample[field]
            b = next_sample[field]
            if a is None or b is None:
                continue
            sample[field] = _round_point([float(a[0]) + (float(b[0]) - float(a[0])) * alpha, float(a[1]) + (float(b[1]) - float(a[1])) * alpha])
        if prev_sample.get("localWidth") is not None and next_sample.get("localWidth") is not None:
            sample["localWidth"] = round(float(prev_sample["localWidth"]) + (float(next_sample["localWidth"]) - float(prev_sample["localWidth"])) * alpha, 6)
        if prev_sample.get("lateralReferenceOffset") is not None and next_sample.get("lateralReferenceOffset") is not None:
            sample["lateralReferenceOffset"] = round(
                float(prev_sample["lateralReferenceOffset"])
                + (float(next_sample["lateralReferenceOffset"]) - float(prev_sample["lateralReferenceOffset"])) * alpha,
                6,
            )
        sample["valid"] = True
        sample["interpolated"] = True
        interpolated += 1
    return interpolated


def _enforce_left_right_orientation(samples: List[Dict[str, Any]]) -> int:
    swapped = 0
    for sample in samples:
        if not sample.get("leftEdge") or not sample.get("rightEdge"):
            continue
        normal = sample["normal"]
        fast = sample["fastLane"]
        left = sample["leftEdge"]
        right = sample["rightEdge"]
        left_dot = (left[0] - fast[0]) * normal[0] + (left[1] - fast[1]) * normal[1]
        right_dot = (right[0] - fast[0]) * normal[0] + (right[1] - fast[1]) * normal[1]
        swapped_left_dot = (right[0] - fast[0]) * normal[0] + (right[1] - fast[1]) * normal[1]
        swapped_right_dot = (left[0] - fast[0]) * normal[0] + (left[1] - fast[1]) * normal[1]
        if left_dot > right_dot:
            continue
        if swapped_left_dot > swapped_right_dot:
            sample["leftEdge"], sample["rightEdge"] = sample["rightEdge"], sample["leftEdge"]
            swapped += 1
        centerline = [
            (float(sample["leftEdge"][0]) + float(sample["rightEdge"][0])) * 0.5,
            (float(sample["leftEdge"][1]) + float(sample["rightEdge"][1])) * 0.5,
        ]
        sample["centerline"] = _round_point(centerline)
        sample["localWidth"] = round(_distance(sample["leftEdge"], sample["rightEdge"]), 6)
        sample["lateralReferenceOffset"] = round(
            (float(fast[0]) - centerline[0]) * normal[0] + (float(fast[1]) - centerline[1]) * normal[1],
            6,
        )
    return swapped


def _edge_metrics(samples: Sequence[Dict[str, Any]], original_invalid: int) -> Dict[str, Any]:
    widths = [float(sample["localWidth"]) for sample in samples if sample.get("localWidth") is not None and sample.get("valid")]
    centerline = [sample["centerline"] for sample in samples if sample.get("centerline")]
    first_last_distance = _distance(centerline[0], centerline[-1]) if len(centerline) > 1 else None
    inconsistent = 0
    fast_lane_outside_edges = 0
    for sample in samples:
        if not sample.get("leftEdge") or not sample.get("rightEdge"):
            continue
        normal = sample["normal"]
        fast = sample["fastLane"]
        left = sample["leftEdge"]
        right = sample["rightEdge"]
        left_dot = (left[0] - fast[0]) * normal[0] + (left[1] - fast[1]) * normal[1]
        right_dot = (right[0] - fast[0]) * normal[0] + (right[1] - fast[1]) * normal[1]
        if left_dot <= right_dot:
            inconsistent += 1
        if not (left_dot >= 0.0 and right_dot <= 0.0):
            fast_lane_outside_edges += 1
    return {
        "validRaycastSamples": len(samples) - original_invalid,
        "invalidRaycastSamples": original_invalid,
        "interpolatedSamples": sum(1 for sample in samples if sample.get("interpolated")),
        "width": {
            "min": round(min(widths), 6) if widths else None,
            "avg": round(sum(widths) / len(widths), 6) if widths else None,
            "max": round(max(widths), 6) if widths else None,
        },
        "centerlineFirstLastDistance": round(first_last_distance, 6) if first_last_distance is not None else None,
        "loopClosed": first_last_distance is not None and first_last_distance <= 5.0,
        "leftRightOrientationConsistent": inconsistent == 0,
        "orientationInconsistencyCount": inconsistent,
        "fastLaneOutsideExtractedEdgesCount": fast_lane_outside_edges,
    }


def _closed_points(samples: Sequence[Dict[str, Any]], field: str) -> List[List[float]]:
    points = [_round_point(sample[field]) for sample in samples if sample.get(field)]
    if points and points[0] != points[-1]:
        points.append(points[0])
    return points


def _bounds_from_points(points: Sequence[Sequence[float]]) -> Optional[Dict[str, float]]:
    if not points:
        return None
    bounds_min, bounds_max = _bounds2()
    for point in points:
        _update_bounds(bounds_min, bounds_max, point)
    return _bounds_payload(bounds_min, bounds_max)


def build_track_edges_from_surface_from_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    diagnostics: List[Dict[str, Any]] = []
    surface = build_track_surface_polygon_from_manifest(manifest)
    triangles = surface.get("triangles", [])
    components, triangle_to_component = _component_analysis(triangles) if triangles else ([], {})
    selected_component = components[0] if components else None
    selected_component_id = int(selected_component["componentId"]) if selected_component else -1
    selected_indices = _selected_triangle_indices(triangle_to_component, selected_component_id) if selected_component else []
    boundary_edges, node_points = _boundary_edges(triangles, selected_indices)
    raw_loops, clean_loops = _build_boundary_loops(boundary_edges, node_points)
    fast_lane = parse_fast_lane_ai((manifest.get("aiFiles") or {}).get("fast_lane"))
    diagnostics.extend(surface.get("diagnostics", []))
    diagnostics.extend(fast_lane.get("diagnostics", []))

    raycast_segments: List[Tuple[List[float], List[float]]] = []
    raycast_source = "clean_boundary_loops_top_2"
    clean_loop_sets = [2, 4, 8, None]
    samples: List[Dict[str, Any]] = []
    raycast_metrics = {"valid": 0, "invalid": fast_lane.get("pointCount", 0)}
    for limit in clean_loop_sets:
        if not clean_loops:
            break
        candidate_segments = _segments_from_loops(clean_loops, limit=limit)
        candidate_samples, candidate_metrics = _run_raycast(fast_lane, candidate_segments)
        if candidate_metrics.get("valid", 0) > raycast_metrics.get("valid", 0):
            samples = candidate_samples
            raycast_metrics = candidate_metrics
            raycast_segments = candidate_segments
            raycast_source = "clean_boundary_loops_all" if limit is None else f"clean_boundary_loops_top_{limit}"
        if fast_lane.get("pointCount") and candidate_metrics.get("valid", 0) / max(1, fast_lane.get("pointCount", 1)) >= 0.92:
            break
    if fast_lane.get("pointCount") and raycast_metrics.get("valid", 0) / max(1, fast_lane.get("pointCount", 1)) < 0.75:
        diagnostics.append({"code": "raycast_clean_loop_fallback", "message": "Clean loops produced too few valid raycasts; using raw selected-component boundary edges"})
        raycast_segments = _segments_from_boundary(boundary_edges)
        samples, raycast_metrics = _run_raycast(fast_lane, raycast_segments)
        raycast_source = "raw_selected_component_boundary"

    original_invalid = raycast_metrics.get("invalid", 0)
    interpolated = _interpolate_samples(samples)
    orientation_swaps = _enforce_left_right_orientation(samples)
    if interpolated:
        diagnostics.append({"code": "raycast_samples_interpolated", "message": "Invalid raycast samples were interpolated from neighboring valid samples", "count": interpolated})
    if orientation_swaps:
        diagnostics.append({"code": "left_right_orientation_corrected", "message": "Interpolated or ambiguous samples were swapped to keep left/right orientation consistent", "count": orientation_swaps})
    metrics = _edge_metrics(samples, original_invalid)
    metrics.update(
        {
            "selectedComponentTriangleCount": selected_component.get("triangleCount") if selected_component else 0,
            "selectedComponentArea": selected_component.get("area") if selected_component else 0,
            "boundaryLoopCount": len(clean_loops),
            "rawBoundaryLoopCount": len(raw_loops),
            "raycastBoundarySource": raycast_source,
            "raycastBoundarySegmentCount": len(raycast_segments),
        }
    )

    centerline = _closed_points(samples, "centerline")
    left_edge = _closed_points(samples, "leftEdge")
    right_edge = _closed_points(samples, "rightEdge")
    return {
        "trackName": manifest.get("trackNameFromSharedMemory"),
        "trackConfig": manifest.get("trackConfigFromSharedMemory"),
        "projection": "mapX = worldX, mapY = -worldZ",
        "surfaceSource": surface.get("source"),
        "fastLaneAi": fast_lane.get("path"),
        "includedSurfaceKeys": surface.get("includedSurfaceKeys", []),
        "components": {
            "count": len(components),
            "selectedComponentId": selected_component_id,
            "items": components,
        },
        "boundary": {
            "selectedComponentBoundarySegmentCount": len(boundary_edges),
            "rawLoops": [
                {key: value for key, value in loop.items() if key != "points"}
                for loop in raw_loops
            ],
            "cleanLoops": clean_loops,
        },
        "fastLane": {
            "version": fast_lane.get("version"),
            "pointCount": fast_lane.get("pointCount"),
            "points": fast_lane.get("points", []),
        },
        "edges": {
            "sampleCount": len(samples),
            "centerline": centerline,
            "leftEdge": left_edge,
            "rightEdge": right_edge,
            "samples": samples,
            "bounds": _bounds_from_points(centerline + left_edge + right_edge),
        },
        "metrics": metrics,
        "diagnostics": diagnostics,
    }


KERB_SURFACES = ("KERB", "CURB")
MIN_KERB_LOOP_AREA = 2.0
MIN_KERB_LOOP_PERIMETER = 6.0
# Kerbs are narrow strips, so the track-body tolerance flattens their curvature
# into visible straight facets. A tighter one keeps the arc of a corner kerb.
KERB_SIMPLIFY_TOLERANCE = 0.06


# Measured against the asphalt that actually gets drawn, not the AI spine. The
# spine runs on past where the surface is rendered -- at pit entry and exit
# especially -- which left kerbs and paint floating in empty space on the map.
MAX_KERB_DISTANCE_FROM_LANE = 6.0
# Painted lines measure well under a metre across; the narrowest drivable mesh at
# Interlagos is the verge at 1.30 m, so this separates paint from surface without
# naming any mesh. Mesh names do not work: roadline003 is 3.47 m of asphalt.
MARKING_MAX_WIDTH_METERS = 1.2
MARKING_SIMPLIFY_TOLERANCE = 0.05
MIN_MARKING_LOOP_AREA = 0.5
MIN_MARKING_LOOP_PERIMETER = 4.0


def _mesh_effective_widths(
    triangles: Sequence[Dict[str, Any]],
    spine: np.ndarray,
) -> Dict[str, float]:
    """Area divided by the length of racing line each mesh actually spans.

    Dividing by a bounding-box diagonal instead makes any mesh that wraps the
    circuit look several times wider than it is, which is what made painted
    lines indistinguishable from asphalt on the first attempt.
    """
    if not len(spine):
        return {}
    segment_lengths = np.hypot(*(np.diff(spine, axis=0).T))
    arc = np.concatenate([[0.0], np.cumsum(segment_lengths)])

    areas: Dict[str, float] = defaultdict(float)
    centroids: Dict[str, List[np.ndarray]] = defaultdict(list)
    for triangle in triangles:
        mesh = str(triangle.get("mesh"))
        areas[mesh] += float(triangle.get("area") or 0.0)
        centroids[mesh].append(np.array(triangle["vertices"], dtype=float)[:, :2].mean(axis=0))

    widths: Dict[str, float] = {}
    for mesh, area in areas.items():
        points = np.array(centroids[mesh])
        deltas = points[:, None, :] - spine[None, :, :]
        nearest = np.sqrt((deltas * deltas).sum(axis=2)).argmin(axis=1)
        covered = arc[nearest]
        span = max(float(np.percentile(covered, 99) - np.percentile(covered, 1)), 1.0)
        widths[mesh] = area / span
    return widths


def build_marking_geometry(
    triangles: Sequence[Dict[str, Any]],
    spine: np.ndarray,
    reference_lanes: Optional[Sequence[np.ndarray]] = None,
    max_width: float = MARKING_MAX_WIDTH_METERS,
) -> Dict[str, Any]:
    """Outline the painted track markings.

    They arrive as ROAD surface like the asphalt itself, so they are told apart
    by how wide they actually are rather than by mesh name or surface key.
    """
    widths = _mesh_effective_widths(
        [t for t in triangles if str(t.get("surface", "")).upper() == "ROAD"], spine
    )
    marking_meshes = {mesh for mesh, width in widths.items() if width < max_width}
    marking_triangles = [
        triangle for triangle in triangles
        if str(triangle.get("surface", "")).upper() == "ROAD"
        and str(triangle.get("mesh")) in marking_meshes
    ]
    if not marking_triangles:
        return {"polygons": [], "triangleCount": 0, "meshes": [], "widths": {}}

    components, triangle_to_component = _component_analysis(marking_triangles)
    polygons: List[Dict[str, Any]] = []
    rejected_far = 0
    for component in components:
        indices = _selected_triangle_indices(triangle_to_component, int(component["componentId"]))
        if not indices:
            continue
        boundary, node_points = _boundary_edges(marking_triangles, indices)
        if not boundary:
            continue
        _, clean_loops = _build_boundary_loops(
            boundary, node_points, MIN_MARKING_LOOP_AREA, MIN_MARKING_LOOP_PERIMETER,
            MARKING_SIMPLIFY_TOLERANCE,
        )
        # A line that runs the whole lap closes a ring around the entire infield,
        # so its outer boundary alone would paint the middle of the circuit. The
        # paint is the band between the outer ring and its holes, so every ring of
        # the component is kept and filled with the even-odd rule.
        rings = [
            loop.get("points", [])
            for loop in clean_loops
            if len(loop.get("points") or []) >= 4
        ]
        if not rings:
            continue
        if reference_lanes:
            outer = np.array(rings[0], dtype=float)
            if _min_distance_to_paths(outer, reference_lanes) > MAX_KERB_DISTANCE_FROM_LANE:
                rejected_far += 1
                continue
        painted = sum(float(marking_triangles[i].get("area") or 0.0) for i in indices)
        polygons.append({"area": round(painted, 3), "rings": rings})

    polygons.sort(key=lambda item: float(item.get("area") or 0.0), reverse=True)
    return {
        "polygons": polygons,
        "triangleCount": len(marking_triangles),
        "rejectedOffLane": rejected_far,
        "maxWidthMeters": max_width,
        "meshes": sorted(marking_meshes),
        "widths": {mesh: round(widths[mesh], 3) for mesh in sorted(marking_meshes)},
    }


# Small enough to keep the asphalt islands the track is made of -- a 77 m2 piece
# by the infield entry was being dropped at 150 -- and large enough to leave the
# stray slivers out.
MIN_DRAWN_ASPHALT_AREA = 20.0

# How far from the track's own edges asphalt may sit and still be drawn. The
# venue is one connected sheet of ROAD in the model -- the paddock and the
# service roads run into the circuit, so a component filter cannot separate them.
# Measured by area against distance from the extracted edges: 84% of the asphalt
# lies within 10 m, 96% within 25 m, and what is past that is the 5271 slivers of
# paddock and access road that were staining the infield. Cutting at 25 m keeps
# the track and its run-off aprons and drops the rest.
MAX_DRAWN_ASPHALT_DISTANCE = 25.0


def _asphalt_reference_lanes(
    reference_lanes: Optional[Sequence[np.ndarray]],
    pit_lane: Optional[Dict[str, Any]],
) -> List[np.ndarray]:
    """What the drawn asphalt is allowed to sit near: the track and the pit lane."""
    lanes = [np.asarray(lane, dtype=float) for lane in (reference_lanes or []) if len(lane)]
    coords = [point.get("mapPosition") for point in ((pit_lane or {}).get("points") or [])]
    pit = np.array([c for c in coords if c], dtype=float)
    if len(pit) >= 2:
        lanes.append(pit)
    return lanes


def build_drawn_asphalt(
    triangles: Sequence[Dict[str, Any]],
    marking_meshes: Sequence[str],
    reference_lanes: Optional[Sequence[np.ndarray]] = None,
    min_area: float = MIN_DRAWN_ASPHALT_AREA,
    max_distance: float = MAX_DRAWN_ASPHALT_DISTANCE,
) -> Dict[str, Any]:
    """Boundary loops of the drivable asphalt, for filling on the map.

    The surface read from the KN5 covers ROAD, CURB and KERB, and the painted
    lines are ROAD like the asphalt is. Every one of those thin strips brings its
    own pair of boundary loops -- the two sides of a stripe a quarter of a metre
    apart -- and each pair flips the even-odd parity of whatever contains it, so
    filling the raw loops paints the infield and hollows out the track.

    So the paint and the kerbs come out before the boundary is traced, which
    removes the cause instead of trying to sort the loops out afterwards. This is
    built only for drawing: the loops the raycast measures against are left
    exactly as they were, kerbs and stripes included.

    Distance from the track's own edges does the rest. The venue is one connected
    sheet of ROAD -- paddock and service roads run into the circuit, so they share
    a component with it and no component filter can tell them apart. Cutting the
    triangles by distance first means the boundary is traced around the track and
    its aprons alone, and the infield comes out empty.
    """
    excluded = {str(mesh) for mesh in marking_meshes or []}
    road = [
        triangle for triangle in triangles
        if str(triangle.get("surface", "")).upper() == "ROAD"
        and str(triangle.get("mesh")) not in excluded
    ]
    lanes = [np.asarray(lane, dtype=float) for lane in (reference_lanes or []) if len(lane)]
    if road and lanes:
        reference = np.vstack(lanes)
        centroids = np.array([np.asarray(t["vertices"], dtype=float).mean(axis=0) for t in road])
        tree = KDTree(reference)
        distances, _ = tree.query(centroids)
        road = [triangle for triangle, distance in zip(road, distances) if distance <= max_distance]
    if not road:
        return {"loops": [], "loopCount": 0, "componentCount": 0, "excludedMeshes": sorted(excluded)}

    components, triangle_to_component = _component_analysis(road)
    loops: List[Dict[str, Any]] = []
    kept_components = 0
    for component in components:
        if float(component.get("area") or 0.0) < min_area:
            continue
        indices = _selected_triangle_indices(triangle_to_component, int(component["componentId"]))
        if not indices:
            continue
        boundary, node_points = _boundary_edges(road, indices)
        if not boundary:
            continue
        _, clean_loops = _build_boundary_loops(boundary, node_points)
        component_loops = [loop for loop in clean_loops if len(loop.get("points") or []) >= 3]
        if not component_loops:
            continue
        kept_components += 1
        for loop in component_loops:
            loops.append({
                "points": loop.get("points"),
                "area": loop.get("area"),
                "classification": loop.get("classification"),
                "componentId": int(component["componentId"]),
            })
    return {
        "loops": loops,
        "loopCount": len(loops),
        "componentCount": kept_components,
        "triangleCount": len(road),
        "excludedMeshes": sorted(excluded),
    }


def _min_distance_to_paths(points: np.ndarray, paths: Sequence[np.ndarray]) -> float:
    best = float("inf")
    for path in paths:
        if not len(path):
            continue
        deltas = points[:, None, :] - path[None, :, :]
        best = min(best, float(np.sqrt((deltas * deltas).sum(axis=2)).min()))
    return best


def build_kerb_geometry(
    triangles: Sequence[Dict[str, Any]],
    reference_lanes: Optional[Sequence[np.ndarray]] = None,
    max_distance_from_lane: float = MAX_KERB_DISTANCE_FROM_LANE,
) -> Dict[str, Any]:
    """Outline the kerbs as their own polygons.

    KERB and CURB triangles are already parsed out of the KN5 alongside ROAD, but
    they were being fused into the single drivable surface and never surfaced, so
    the map had no kerbs to draw. Kerb strips are far smaller than the track body,
    so the default loop area/perimeter floors would discard them; this uses floors
    sized for them instead.
    """
    kerb_triangles = [
        triangle for triangle in triangles
        if str(triangle.get("surface", "")).upper() in KERB_SURFACES
    ]
    if not kerb_triangles:
        return {"polygons": [], "triangleCount": 0, "componentCount": 0, "surfaces": list(KERB_SURFACES)}

    components, triangle_to_component = _component_analysis(kerb_triangles)
    polygons: List[Dict[str, Any]] = []
    rejected_far = 0
    for component in components:
        component_id = int(component["componentId"])
        indices = _selected_triangle_indices(triangle_to_component, component_id)
        if not indices:
            continue
        boundary, node_points = _boundary_edges(kerb_triangles, indices)
        if not boundary:
            continue
        _, clean_loops = _build_boundary_loops(
            boundary, node_points, MIN_KERB_LOOP_AREA, MIN_KERB_LOOP_PERIMETER,
            KERB_SIMPLIFY_TOLERANCE,
        )
        surfaces = {str(kerb_triangles[i].get("surface", "")).upper() for i in indices}
        for loop in clean_loops:
            # Only the outer ring of each strip is useful for filling it.
            if loop.get("classification") != "external":
                continue
            # Simplification recomputes area, and it can collapse a very thin strip
            # to nothing after it passed the pre-simplification floor.
            if float(loop.get("area") or 0.0) < MIN_KERB_LOOP_AREA or len(loop.get("points") or []) < 4:
                continue
            # A track model covers the whole venue, so KERB/CURB also matches kerbs
            # on layouts and service areas the driver never sees. Keeping only those
            # that hug a lane the car can actually use -- the racing line or the pit
            # lane -- drops those without hand-listing anything track-specific.
            if reference_lanes:
                ring = np.array(loop.get("points"), dtype=float)
                distance = _min_distance_to_paths(ring, reference_lanes)
                if distance > max_distance_from_lane:
                    rejected_far += 1
                    continue
            polygons.append(
                {
                    "componentId": component_id,
                    "surface": "KERB" if "KERB" in surfaces else "CURB",
                    "area": loop.get("area"),
                    "perimeter": loop.get("perimeter"),
                    "points": loop.get("points", []),
                }
            )

    polygons.sort(key=lambda item: float(item.get("area") or 0.0), reverse=True)
    return {
        "polygons": polygons,
        "triangleCount": len(kerb_triangles),
        "componentCount": len(components),
        "rejectedOffLane": rejected_far,
        "maxDistanceFromLane": max_distance_from_lane if reference_lanes else None,
        "surfaces": sorted({str(p.get("surface")) for p in polygons}),
    }


def build_track_edges_interval_raycast_from_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    diagnostics: List[Dict[str, Any]] = []
    surface = build_track_surface_polygon_from_manifest(manifest)
    triangles = surface.get("triangles", [])
    components, triangle_to_component = _component_analysis(triangles) if triangles else ([], {})
    selected_component = components[0] if components else None
    selected_component_id = int(selected_component["componentId"]) if selected_component else -1
    selected_indices = _selected_triangle_indices(triangle_to_component, selected_component_id) if selected_component else []
    boundary_edges, node_points = _boundary_edges(triangles, selected_indices)
    raw_loops, clean_loops = _build_boundary_loops(boundary_edges, node_points)
    fast_lane = parse_fast_lane_ai((manifest.get("aiFiles") or {}).get("fast_lane"))
    diagnostics.extend(surface.get("diagnostics", []))
    diagnostics.extend(fast_lane.get("diagnostics", []))

    surface_index = _TriangleSurfaceIndex(triangles, selected_indices)
    samples, raycast_metrics = _run_interval_raycast(fast_lane, clean_loops, surface_index)
    original_invalid = raycast_metrics.get("invalid", 0)
    discontinuous = _reject_discontinuous_fallback_samples(samples)
    if discontinuous:
        diagnostics.append({
            "code": "discontinuous_fallback_samples_rejected",
            "message": "Samples that fell back to the nearest interval and jumped to a different asphalt strip were dropped for interpolation",
            "count": discontinuous,
        })
    interpolated = _interpolate_samples(samples)
    orientation_swaps = _enforce_left_right_orientation(samples)
    if interpolated:
        diagnostics.append({"code": "raycast_samples_interpolated", "message": "Invalid interval raycast samples were interpolated from neighboring valid samples", "count": interpolated})
    if orientation_swaps:
        diagnostics.append({"code": "left_right_orientation_corrected", "message": "Interpolated or ambiguous samples were swapped to keep left/right orientation consistent", "count": orientation_swaps})

    metrics = _edge_metrics(samples, original_invalid)
    interval_containing = sum(1 for sample in samples if sample.get("selectedIntervalContainsFastLane"))
    corrected = sum(1 for sample in samples if sample.get("correctionReason") == "corrected_from_nearest_interval")
    metrics.update(
        {
            "selectedComponentTriangleCount": selected_component.get("triangleCount") if selected_component else 0,
            "selectedComponentArea": selected_component.get("area") if selected_component else 0,
            "boundaryLoopCount": len(clean_loops),
            "rawBoundaryLoopCount": len(raw_loops),
            "raycastBoundarySource": "clean_boundary_loops_interval_all",
            "raycastBoundarySegmentCount": len(_segments_from_loops_with_metadata(clean_loops)),
            "intervalsContainingFastLane": interval_containing,
            "samplesCorrectedFromNearestInterval": corrected,
            "intervalMaxPlausibleWidth": MAX_INTERVAL_TRACK_WIDTH,
        }
    )

    # Kerbs come from the same parsed surface, but as their own outlines so the
    # map can draw them instead of fusing them into the drivable asphalt.
    # The racing line and the pit lane are the two lanes a car can be on; kerbs
    # that hug neither belong to another part of the venue in the same model.
    pit_lane_path = (manifest.get("aiFiles") or {}).get("pit_lane")
    pit_lane = parse_fast_lane_ai(pit_lane_path) if pit_lane_path else None
    reference_lanes = []
    for edge_key in ("leftEdge", "rightEdge"):
        edge = np.array(
            [sample[edge_key] for sample in samples if sample.get(edge_key)], dtype=float
        )
        if len(edge) >= 2:
            reference_lanes.append(edge)
    if not reference_lanes:
        # No usable band yet, so fall back to the lanes rather than dropping everything.
        for lane in (fast_lane, pit_lane):
            if not lane:
                continue
            coords = [point.get("mapPosition") for point in lane.get("points", []) or []]
            array = np.array([c for c in coords if c], dtype=float)
            if len(array) >= 2:
                reference_lanes.append(array)
    kerbs = build_kerb_geometry(triangles, reference_lanes)
    markings = build_marking_geometry(
        triangles,
        reference_lanes[0] if reference_lanes else np.empty((0, 2)),
        reference_lanes,
    )
    # The paint arrives undifferentiated: the track limit, the pit lane limit and
    # the paint around an access road are all just rings. The map has to tell them
    # apart, so classify them here against the two lanes the game ships.
    try:
        classify_marking_rings(markings, fast_lane, pit_lane)
    except Exception:
        logger.exception("Marking classification failed; the map will fall back to unclassified paint")
        markings.setdefault("features", [])
        markings.setdefault("classification", {"status": "FAILED"})
    metrics["markingGroupCount"] = len(markings.get("polygons", []))
    metrics["markingFeatureCount"] = len(markings.get("features", []))
    metrics["kerbPolygonCount"] = len(kerbs.get("polygons", []))
    metrics["kerbTriangleCount"] = kerbs.get("triangleCount", 0)

    centerline = _closed_points(samples, "centerline")
    left_edge = _closed_points(samples, "leftEdge")
    right_edge = _closed_points(samples, "rightEdge")
    return {
        "kerbs": kerbs,
        "markings": markings,
        # The asphalt as the game models it, for the map to fill. Kept apart from
        # `asphaltPolygon`, which the paint correction rewrites into a band built
        # from the reconstructed edges -- these loops are the mesh itself and
        # must not be overwritten by anything the raycast produced.
        "asphaltSurface": {
            # The pit lane joins the track's own edges as a reference: it runs far
            # enough from them that a cut measured on the edges alone took the pit
            # asphalt out from under its own paint.
            **build_drawn_asphalt(
                triangles,
                markings.get("meshes") or [],
                _asphalt_reference_lanes(reference_lanes, pit_lane),
            ),
            "source": surface.get("source"),
        },
        "trackName": manifest.get("trackNameFromSharedMemory"),
        "trackConfig": manifest.get("trackConfigFromSharedMemory"),
        "projection": "mapX = worldX, mapY = -worldZ",
        "surfaceSource": surface.get("source"),
        "fastLaneAi": fast_lane.get("path"),
        "includedSurfaceKeys": surface.get("includedSurfaceKeys", []),
        "raycastAlgorithm": "inside_surface_interval_containing_fast_lane",
        "components": {
            "count": len(components),
            "selectedComponentId": selected_component_id,
            "items": components,
        },
        "boundary": {
            "selectedComponentBoundarySegmentCount": len(boundary_edges),
            "rawLoops": [
                {key: value for key, value in loop.items() if key != "points"}
                for loop in raw_loops
            ],
            "cleanLoops": clean_loops,
        },
        "fastLane": {
            "version": fast_lane.get("version"),
            "pointCount": fast_lane.get("pointCount"),
            "points": fast_lane.get("points", []),
        },
        "edges": {
            "sampleCount": len(samples),
            "centerline": centerline,
            "leftEdge": left_edge,
            "rightEdge": right_edge,
            "samples": samples,
            "bounds": _bounds_from_points(centerline + left_edge + right_edge),
        },
        "metrics": metrics,
        "diagnostics": diagnostics,
    }


def _safe_track_name(track: Optional[str]) -> str:
    value = track or "unknown"
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def write_track_edges_debug_files(result: Dict[str, Any], output_dir: Path) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_track = _safe_track_name(result.get("trackName"))
    components_path = output_dir / f"track_surface_components_{safe_track}.json"
    boundary_path = output_dir / f"track_boundary_loops_{safe_track}.json"
    edges_path = output_dir / f"track_edges_from_surface_{safe_track}.json"
    svg_path = output_dir / f"track_edges_preview_{safe_track}.svg"

    components_payload = {
        "trackName": result.get("trackName"),
        "trackConfig": result.get("trackConfig"),
        "projection": result.get("projection"),
        "components": result.get("components"),
        "diagnostics": result.get("diagnostics", []),
    }
    boundary_payload = {
        "trackName": result.get("trackName"),
        "trackConfig": result.get("trackConfig"),
        "projection": result.get("projection"),
        "boundary": result.get("boundary"),
        "diagnostics": result.get("diagnostics", []),
    }
    components_path.write_text(json.dumps(components_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    boundary_path.write_text(json.dumps(boundary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    edges_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    svg_path.write_text(build_track_edges_svg(result), encoding="utf-8")
    return {
        "components": str(components_path),
        "boundaryLoops": str(boundary_path),
        "edges": str(edges_path),
        "svg": str(svg_path),
    }


def _svg_polyline(points: Sequence[Sequence[float]], project, *, stroke: str, width: float, opacity: float = 1.0, dash: Optional[str] = None) -> str:
    if len(points) < 2:
        return ""
    text = " ".join(f"{project(point)[0]:.2f},{project(point)[1]:.2f}" for point in points)
    dash_text = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{text}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-opacity="{opacity}" stroke-linejoin="round" stroke-linecap="round"{dash_text}/>'


def build_track_edges_svg(result: Dict[str, Any]) -> str:
    bounds = result.get("edges", {}).get("bounds")
    if not bounds:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="700"><text x="20" y="40">No extracted edges</text></svg>'
    margin = 24
    width, height = 1100, 900
    min_x, max_x = bounds["minX"], bounds["maxX"]
    min_y, max_y = bounds["minY"], bounds["maxY"]
    scale = min((width - margin * 2) / max(max_x - min_x, 1.0), (height - margin * 2) / max(max_y - min_y, 1.0))

    def project(point: Sequence[float]) -> Tuple[float, float]:
        x = margin + (float(point[0]) - min_x) * scale
        y = height - margin - (float(point[1]) - min_y) * scale
        return x, y

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#080b10"/>',
    ]
    for loop in result.get("boundary", {}).get("cleanLoops", []):
        stroke = "#27d8ff" if loop.get("classification") == "external" else "#d8dde7"
        opacity = 0.95 if loop.get("classification") == "external" else 0.72
        parts.append(_svg_polyline(loop.get("points", []), project, stroke=stroke, width=1.5, opacity=opacity))
    fast_lane = [point["mapPosition"] for point in result.get("fastLane", {}).get("points", [])]
    parts.append(_svg_polyline(fast_lane, project, stroke="#f4b350", width=1.0, opacity=0.75, dash="5 6"))
    parts.append(_svg_polyline(result.get("edges", {}).get("leftEdge", []), project, stroke="#4aa3ff", width=2.0, opacity=0.9))
    parts.append(_svg_polyline(result.get("edges", {}).get("rightEdge", []), project, stroke="#ff637d", width=2.0, opacity=0.9))
    parts.append(_svg_polyline(result.get("edges", {}).get("centerline", []), project, stroke="#5dff9a", width=1.6, opacity=0.9))
    for sample in result.get("edges", {}).get("samples", [])[::20]:
        if not sample.get("centerline") or not sample.get("leftEdge") or not sample.get("rightEdge"):
            continue
        lx, ly = project(sample["leftEdge"])
        rx, ry = project(sample["rightEdge"])
        parts.append(f'<line x1="{lx:.2f}" y1="{ly:.2f}" x2="{rx:.2f}" y2="{ry:.2f}" stroke="#6f7785" stroke-width="0.45" stroke-opacity="0.45"/>')
    parts.append(f'<text x="24" y="32" fill="#d9e6f2" font-family="Segoe UI, Arial" font-size="16">KN5 surface-derived edges - {result.get("trackName")}</text>')
    parts.append("</svg>")
    return "\n".join(part for part in parts if part)
