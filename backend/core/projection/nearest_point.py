import numpy as np
from typing import Any, Dict, Optional, Tuple


def project_point_to_segment(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> Tuple[np.ndarray, float, float]:
    segment = end - start
    length_sq = float(np.dot(segment, segment))
    if length_sq <= 1e-12:
        return start, 0.0, float(np.dot(point - start, point - start))

    t = float(np.dot(point - start, segment) / length_sq)
    t_clamped = float(np.clip(t, 0.0, 1.0))
    projected = start + segment * t_clamped
    dist_sq = float(np.dot(point - projected, point - projected))
    return projected, t_clamped, dist_sq


def nearest_segment_projection(
    point: np.ndarray,
    points: np.ndarray,
    distances: np.ndarray,
    total_length: float,
    tree: Optional[Any] = None,
    k: int = 8,
    closed_loop: bool = True,
) -> Dict[str, Any]:
    """Project a world X/Z point onto the nearest centerline segment."""
    if len(points) < 2:
        raise ValueError("Projection requires at least two centerline points")

    segment_count = len(points) if closed_loop else len(points) - 1
    candidate_indices = range(segment_count)
    if tree is not None:
        k = min(k, len(points))
        _, idxs = tree.query(point, k=k)
        idxs = np.atleast_1d(idxs)
        expanded = set()
        for idx in idxs:
            i = int(idx)
            if closed_loop:
                expanded.add((i - 1) % len(points))
                expanded.add(i % len(points))
                expanded.add((i + 1) % len(points))
            else:
                for candidate in (i - 1, i, i + 1):
                    if 0 <= candidate < segment_count:
                        expanded.add(candidate)
        candidate_indices = expanded

    best = {
        "segment_index": 0,
        "segment_t": 0.0,
        "distance_sq": float("inf"),
        "projected_point": points[0],
        "distance_along_track": 0.0,
        "segment_vector": points[1] - points[0],
    }

    for idx in candidate_indices:
        i = int(idx)
        j = (i + 1) % len(points) if closed_loop else i + 1
        start = points[i]
        end = points[j]
        projected, t, dist_sq = project_point_to_segment(point, start, end)
        if dist_sq < best["distance_sq"]:
            start_s = float(distances[i])
            end_s = float(distances[j]) if j > i else float(total_length)
            distance_along = start_s + (end_s - start_s) * t
            if closed_loop:
                distance_along = distance_along % total_length
            best.update(
                {
                    "segment_index": i,
                    "segment_t": t,
                    "distance_sq": dist_sq,
                    "projected_point": projected,
                    "distance_along_track": distance_along,
                    "segment_vector": end - start,
                }
            )

    return best
