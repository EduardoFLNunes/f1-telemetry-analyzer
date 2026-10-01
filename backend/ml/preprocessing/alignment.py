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
**oposto** do `lateralOffset` que o runtime grava; `samples.flatten` ja entrega
o gravado convertido (`lateral_recorded`), pela funcao unica
`core.projection.lateral_offset.to_left_positive`.

A projecao gravada nao e usada, mas e medida: `recorded_s_p95_m` e
`recorded_lateral_p95_m` dizem o quanto ela concorda com a recalculada. Uma
volta gravada contra a mesma geometria concorda dentro de centimetros a meio
metro; uma gravada contra outra versao da geometria aparece aqui com metros de
diferenca, e e assim que se identifica com que geometria cada volta foi gravada.
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
    # Concordancia entre a projecao gravada pelo runtime e a recalculada aqui.
    # NaN quando a volta nao gravou a projecao.
    recorded_s_p95_m: float = float("nan")
    recorded_lateral_p95_m: float = float("nan")
    recorded_lateral_correlation: float = float("nan")

    def to_dict(self) -> Dict[str, float]:
        return {
            "coverage": self.coverage,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "backward_steps": self.backward_steps,
            "backward_meters": self.backward_meters,
            "span_m": self.span_m,
            "recorded_s_p95_m": self.recorded_s_p95_m,
            "recorded_lateral_p95_m": self.recorded_lateral_p95_m,
            "recorded_lateral_correlation": self.recorded_lateral_correlation,
        }


# Abaixo disto a comparacao nao tem amostras suficientes para um percentil.
MIN_RECORDED_SAMPLES = 50


def recorded_agreement(
    frame: pd.DataFrame, s_values: np.ndarray, lateral: np.ndarray, track_length: float
) -> Dict[str, float]:
    """O quanto a projecao gravada concorda com a recalculada.

    `s` e comparado circularmente (a linha de chegada e o mesmo ponto em 0 e em
    `track_length`). `lateral_recorded` ja esta na convencao do `ml`; uma
    correlacao negativa aqui quer dizer que alguem trocou o sinal de novo.
    """
    out = {
        "recorded_s_p95_m": float("nan"),
        "recorded_lateral_p95_m": float("nan"),
        "recorded_lateral_correlation": float("nan"),
    }
    if "s_recorded" in frame.columns:
        recorded = frame["s_recorded"].to_numpy(dtype=float)
        usable = np.isfinite(recorded)
        if usable.sum() >= MIN_RECORDED_SAMPLES:
            diff = np.mod(recorded[usable] - s_values[usable] + track_length / 2.0, track_length)
            out["recorded_s_p95_m"] = float(np.percentile(np.abs(diff - track_length / 2.0), 95))
    if "lateral_recorded" in frame.columns:
        recorded = frame["lateral_recorded"].to_numpy(dtype=float)
        usable = np.isfinite(recorded) & np.isfinite(lateral)
        if usable.sum() >= MIN_RECORDED_SAMPLES:
            out["recorded_lateral_p95_m"] = float(
                np.percentile(np.abs(recorded[usable] - lateral[usable]), 95)
            )
            if np.std(recorded[usable]) > 1e-9 and np.std(lateral[usable]) > 1e-9:
                out["recorded_lateral_correlation"] = float(
                    np.corrcoef(recorded[usable], lateral[usable])[0, 1]
                )
    return out


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
        **recorded_agreement(out, s_values, lateral, track.length),
    )
    return out, report
