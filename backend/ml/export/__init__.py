"""Ponte do subsistema para o aplicativo: artefatos que o backend le sozinho."""

from .coaching import (
    COACH_MICROSECTORS,
    FORMAT_VERSION,
    OptimalLineTargets,
    build_targets,
    progress_to_distance,
)

__all__ = [
    "COACH_MICROSECTORS",
    "FORMAT_VERSION",
    "OptimalLineTargets",
    "build_targets",
    "progress_to_distance",
]
