"""A ponte entre uma trajetoria candidata e a rede substituta.

O algoritmo evolutivo produz vetores de deslocamento lateral. A rede substituta
espera os atributos com que foi treinada -- pista, forma da trajetoria e
contexto. Este modulo faz a traducao, e faz uma vez so o que e fixo: os
atributos de pista sao os mesmos para toda trajetoria e para toda geracao, e
recalcula-los 80 vezes por geracao dominaria o custo da busca.
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd

from ..features.engineering import track_features
from ..models.reference_line import neutral_context
from ..models.sequences import SURROGATE_TASK, TaskSpec
from ..track.corners import Corner
from ..track.geometry import TrackGeometry
from ..track.trajectory import curvature as trajectory_curvature
from ..track.trajectory import lateral_derivative


class SurrogateFeatures:
    """Callable (laterais) -> tensor de entrada da rede substituta."""

    def __init__(
        self,
        track: TrackGeometry,
        corners: Optional[Sequence[Corner]] = None,
        context: Optional[Dict[str, float]] = None,
        task: TaskSpec = SURROGATE_TASK,
        trained=None,
    ):
        self.track = track
        self.task = task
        base = track_features(track, corners).copy()
        # O contexto sai do proprio modelo substituto, pelo mesmo motivo que na
        # rede geradora: e onde ele esta calibrado.
        for name, value in {**neutral_context(trained, task), **(context or {})}.items():
            base[name] = float(value)
        self.base = base
        self.columns = list(task.inputs)

        missing = [
            column
            for column in self.columns
            if column not in base.columns
            and column
            not in (
                "lateral",
                "lateral_rate",
                "path_curvature",
                "distance_to_left_edge",
                "distance_to_right_edge",
            )
        ]
        if missing:
            raise KeyError(f"a ponte nao sabe montar os atributos {missing}")

    def __call__(self, laterals: np.ndarray) -> np.ndarray:
        batch = np.atleast_2d(np.asarray(laterals, dtype=float))
        out = np.empty((batch.shape[0], self.track.size, len(self.columns)), dtype=np.float32)
        for index, lateral in enumerate(batch):
            frame = self.base.copy()
            frame["lateral"] = lateral
            frame["lateral_rate"] = lateral_derivative(self.track, lateral)
            frame["path_curvature"] = trajectory_curvature(self.track, lateral)
            frame["distance_to_left_edge"] = self.track.width_left - lateral
            frame["distance_to_right_edge"] = self.track.width_right + lateral
            out[index] = np.nan_to_num(
                frame.reindex(columns=self.columns).to_numpy(dtype=np.float32), nan=0.0
            )
        return out
