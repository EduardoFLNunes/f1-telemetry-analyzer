"""O modelo serve para voltas que ele nunca viu?

A divisao e por sessao, entao "nunca viu" aqui quer dizer sessao inteira de
fora: outro acerto de carro, outra carga de combustivel, outra condicao de
pista. E a medida dura, e a que interessa -- um corte por volta daria numeros
muito melhores e sem significado, porque voltas vizinhas da mesma sessao sao
quase a mesma volta.

As metricas sao reportadas em **unidades fisicas**: metros de trajetoria,
km/h de velocidade, segundos de tempo. A perda de treino vive em espaco
normalizado e nao diz nada a ninguem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

from ..models.sequences import SequenceSet
from ..models.training import TrainedModel


@dataclass
class ChannelError:
    """Erro de um canal num conjunto."""

    channel: str
    unit: str
    mae: float
    rmse: float
    maximum: float
    median: float
    p95: float
    correlation: float
    skill: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "channel": self.channel,
            "unit": self.unit,
            "mae": self.mae,
            "rmse": self.rmse,
            "max": self.maximum,
            "median": self.median,
            "p95": self.p95,
            "correlation": self.correlation,
            "skill": self.skill,
        }


UNITS = {
    "lateral": "m",
    "speed_kmh": "km/h",
    "brake": "0-1",
    "throttle": "0-1",
    "step_time_s": "s",
}


def channel_errors(trained: TrainedModel, dataset: SequenceSet) -> List[ChannelError]:
    """Erro por canal, em unidades fisicas."""
    predicted = trained.predict(dataset.inputs)
    actual = np.asarray(dataset.targets, dtype=float)

    out: List[ChannelError] = []
    for index, channel in enumerate(dataset.target_columns):
        estimate = predicted[..., index].ravel()
        truth = actual[..., index].ravel()
        residual = np.abs(estimate - truth)
        spread = float(np.std(truth))
        rmse = float(np.sqrt(np.mean((estimate - truth) ** 2)))
        correlation = (
            float(np.corrcoef(estimate, truth)[0, 1])
            if np.std(estimate) > 1e-12 and spread > 1e-12
            else float("nan")
        )
        out.append(
            ChannelError(
                channel=channel,
                unit=UNITS.get(channel, ""),
                mae=float(np.mean(residual)),
                rmse=rmse,
                maximum=float(np.max(residual)),
                median=float(np.median(residual)),
                p95=float(np.percentile(residual, 95)),
                correlation=correlation,
                skill=float(1.0 - rmse / spread) if spread > 1e-12 else float("nan"),
            )
        )
    return out


@dataclass
class HoldoutReport:
    """Erro do mesmo modelo nos tres conjuntos."""

    task: str
    splits: Dict[str, List[ChannelError]] = field(default_factory=dict)
    lap_errors: Dict[str, float] = field(default_factory=dict)

    def gap(self, channel: str) -> float:
        """Quantas vezes o erro de teste e maior que o de treino."""
        train = next((c for c in self.splits.get("train", []) if c.channel == channel), None)
        test = next((c for c in self.splits.get("test", []) if c.channel == channel), None)
        if not train or not test or train.mae <= 0:
            return float("nan")
        return test.mae / train.mae

    def to_dict(self) -> Dict[str, object]:
        return {
            "task": self.task,
            "splits": {
                name: [error.to_dict() for error in errors] for name, errors in self.splits.items()
            },
            "lap_errors": self.lap_errors,
            "generalisation_gap": {
                error.channel: self.gap(error.channel) for error in self.splits.get("test", [])
            },
        }


def holdout(
    trained: TrainedModel, sets: Dict[str, SequenceSet], task_name: str
) -> HoldoutReport:
    """Erro do modelo em cada conjunto."""
    return HoldoutReport(
        task=task_name,
        splits={name: channel_errors(trained, dataset) for name, dataset in sets.items() if len(dataset)},
    )


def per_lap_error(
    trained: TrainedModel, dataset: SequenceSet, channel: int = 0
) -> Dict[str, float]:
    """Erro medio de um canal, volta a volta.

    Serve para descobrir se o erro esta espalhado ou concentrado. Um erro medio
    de 1,6 m pode ser 1,6 m em toda parte, ou 0,3 m em quase tudo com algumas
    voltas muito ruins -- e a diferenca decide o que fazer a respeito.
    """
    predicted = trained.predict(dataset.inputs)
    residual = np.abs(predicted[..., channel] - np.asarray(dataset.targets, dtype=float)[..., channel])
    out: Dict[str, float] = {}
    for lap_id in np.unique(dataset.lap_ids):
        mask = dataset.lap_ids == lap_id
        out[str(lap_id)] = float(residual[mask].mean())
    return out


def unknown_lap(
    trained: TrainedModel,
    dataset: SequenceSet,
    lap_id: str,
) -> Dict[str, object]:
    """Todas as metricas para uma volta especifica que o modelo nunca viu."""
    mask = dataset.lap_ids == lap_id
    if not mask.any():
        raise KeyError(f"a volta {lap_id} nao esta neste conjunto")

    subset = SequenceSet(
        inputs=dataset.inputs[mask],
        targets=dataset.targets[mask],
        lap_ids=dataset.lap_ids[mask],
        start_index=dataset.start_index[mask],
        input_columns=dataset.input_columns,
        target_columns=dataset.target_columns,
    )
    return {
        "lap_id": lap_id,
        "windows": int(mask.sum()),
        "channels": [error.to_dict() for error in channel_errors(trained, subset)],
    }
