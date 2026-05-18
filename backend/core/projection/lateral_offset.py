import numpy as np
from typing import Tuple


def normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        return np.array([1.0, 0.0], dtype=float)
    return vector / norm


def tangent_and_normal(segment_vector: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    tangent = normalize(segment_vector)
    normal = np.array([-tangent[1], tangent[0]], dtype=float)
    return tangent, normal


def signed_lateral_offset(world_point: np.ndarray, projected_point: np.ndarray, normal: np.ndarray) -> float:
    return float(np.dot(world_point - projected_point, normal))
