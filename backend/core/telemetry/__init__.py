import math
import numpy as np

from core.projection.nearest_point import nearest_segment_projection


def calculate_map_matching(car_x, car_z, centerline_x_list, centerline_z_list):
    """
    Return the nearest centerline segment projection and lateral distance.
    """
    if not centerline_x_list or not centerline_z_list:
        return car_x, car_z, 0.0

    points = np.column_stack([centerline_x_list, centerline_z_list]).astype(float)
    if len(points) < 2:
        return car_x, car_z, 0.0

    deltas = np.linalg.norm(np.diff(points, axis=0), axis=1)
    loop_delta = np.linalg.norm(points[-1] - points[0])
    distances = np.concatenate([[0.0], np.cumsum(deltas)])
    total_length = float(distances[-1] + loop_delta)

    projected = nearest_segment_projection(
        np.array([car_x, car_z], dtype=float),
        points,
        distances,
        total_length,
    )
    snapped_x, snapped_z = projected["projected_point"]
    lateral_offset = math.sqrt(projected["distance_sq"])

    return float(snapped_x), float(snapped_z), float(lateral_offset)
