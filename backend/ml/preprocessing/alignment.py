"""Alinhamento espacial: de amostras no tempo para amostras na pista.

Duas voltas do mesmo piloto nunca tem o mesmo numero de amostras nem os mesmos
instantes, entao compara-las quadro a quadro compara pontos diferentes da pista.
O eixo comum e a distancia percorrida, e e ela que este modulo produz.

O `s` e sempre recalculado aqui, nunca lido do arquivo. Tres razoes, todas
medidas: seis sessoes gravaram `distanceAlongTrack` como `null`; as que
gravaram usaram versoes diferentes da geometria; e o `lateralOffset` gravado
tem sinal oposto ao da propria normal do arquivo de geometria.

Sinal de `lateral`: positivo e a esquerda da centerline, o mesmo lado para onde
aponta a normal do cache de geometria (`boundsLeft` cai em +normal). E o
**oposto** do `lateralOffset` que o runtime grava -- nao alinhe um com o outro
sem trocar o sinal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from ..track.geometry import TrackGeometry


@dataclass
class AlignmentReport:
    coverage: float          # fracao do comprimento da pista percorrida
    start_s: float
    end_s: float
    backward_steps: int      # amostras em que o carro andou para tras
    backward_meters: float
    span_m: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "coverage": self.coverage,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "backward_steps": self.backward_steps,
            "backward_meters": self.backward_meters,
            "span_m": self.span_m,
        }


def _elapsed(frame: pd.DataFrame) -> np.ndarray:
    """Tempo decorrido dentro da volta, em segundos, comecando em zero.

    O cronometro do jogo (`lap_time_s`) e a fonte boa porque zera na linha. Onde
    ele nao presta -- constante, ausente, ou andando para tras -- vale o relogio
    de parede, que nao zera mas cujas diferencas continuam corretas.
    """
    if "lap_time_s" in frame.columns:
        values = frame["lap_time_s"].to_numpy(dtype=float)
        finite = np.isfinite(values)
        if finite.sum() > 2:
            usable = values[finite]
            grew = usable[-1] - usable[0]
            monotonic = np.all(np.diff(usable) >= -1e-6)
            if grew > 1.0 and monotonic:
                return values - np.nanmin(values)

    if "timestamp_s" in frame.columns:
        values = frame["timestamp_s"].to_numpy(dtype=float)
        if np.isfinite(values).sum() > 2:
            return values - np.nanmin(values)

    return np.arange(len(frame), dtype=float) / 20.0


def unwrap_distance(s_values: np.ndarray, track_length: float) -> np.ndarray:
    """Distancia acumulada sem o salto da linha de chegada.

    Entre duas amostras o carro anda alguns metros; o `s` bruto pula de 4333
    para 1 quando ele cruza a linha. O passo real e o menor deslocamento
    congruente, o que tambem trata o carro andando para tras sem inventar uma
    volta inteira de recuo.
    """
    if s_values.size == 0:
        return s_values
    steps = np.diff(s_values)
    steps = np.mod(steps + track_length / 2.0, track_length) - track_length / 2.0
    return np.concatenate([[s_values[0]], s_values[0] + np.cumsum(steps)])


def align_lap(frame: pd.DataFrame, track: TrackGeometry) -> tuple:
    """Acrescenta `s`, `lateral`, `s_unwrapped` e `elapsed_s`. Retorna (frame, relatorio)."""
    out = frame.copy()
    if out.empty:
        return out, AlignmentReport(0.0, 0.0, 0.0, 0, 0.0, 0.0)

    positions = np.column_stack(
        [out["x"].to_numpy(dtype=float), out["z"].to_numpy(dtype=float)]
    )
    s_values, lateral = track.project_sequence(positions)
    unwrapped = unwrap_distance(s_values, track.length)

    steps = np.diff(unwrapped)
    backward = steps < 0
    out["s"] = s_values
    out["lateral"] = lateral
    out["s_unwrapped"] = unwrapped
    out["elapsed_s"] = _elapsed(out)

    span = float(unwrapped[-1] - unwrapped[0])
    report = AlignmentReport(
        coverage=span / track.length,
        start_s=float(s_values[0]),
        end_s=float(s_values[-1]),
        backward_steps=int(backward.sum()),
        backward_meters=float(-steps[backward].sum()) if backward.any() else 0.0,
        span_m=span,
    )
    return out, report
