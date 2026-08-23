"""Reamostragem de uma volta alinhada para a grade fixa de distancia.

Depois daqui toda volta tem exatamente o mesmo numero de linhas, e a linha `i`
de qualquer volta e o mesmo ponto da pista em qualquer outra. E isso que torna
possivel somar, subtrair e cruzar voltas -- e o que o algoritmo evolutivo exige
para que crossover entre duas trajetorias signifique alguma coisa.

Uma volta comeca e termina na linha de chegada, entao ela cobre a pista inteira
com um buraco de poucos metros no proprio corte. A interpolacao fecha esse
buraco circularmente: a ultima amostra da volta e a primeira estao a um passo de
amostragem de distancia no tempo real, e nao a uma volta.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Sequence

import numpy as np
import pandas as pd

from ..track.geometry import TrackGeometry

# Canais em radianos que dao a volta em 2*pi. Interpolar -3,14 com +3,14 pela
# media da uma direcao para o lado oposto do correto.
ANGULAR_CHANNELS = ("heading",)

# Canais que nao devem ser interpolados: o valor entre duas marchas nao e 3,5.
DISCRETE_CHANNELS = ("gear", "lap_number")

# Colunas que descrevem a amostragem original e nao a pilotagem.
DROPPED_CHANNELS = (
    "timestamp_s",
    "session_time_s",
    "s",
    "s_unwrapped",
    "s_recorded",
    "lateral_offset_recorded",
)


def _interp_circular(
    grid_targets: np.ndarray,
    positions: np.ndarray,
    values: np.ndarray,
    wrap_value: float,
    wrap_position: float,
) -> np.ndarray:
    """Interpola fechando o laco em `wrap_position` com `wrap_value`.

    Sem o ponto de fechamento, `np.interp` repete o ultimo valor no trecho entre
    a ultima amostra e a linha de chegada -- e esse trecho e exatamente a saida
    da ultima curva, onde a velocidade ainda esta subindo.
    """
    if wrap_position <= positions[-1]:
        wrap_position = positions[-1] + 1e-6
    extended_x = np.concatenate([positions, [wrap_position]])
    extended_y = np.concatenate([values, [wrap_value]])
    return np.interp(grid_targets, extended_x, extended_y)


def _closing_time(
    positions: np.ndarray, elapsed: np.ndarray, wrap_position: float
) -> float:
    """Tempo estimado no ponto que fecha a volta.

    Extrapola a ultima velocidade observada pelo trecho que a gravacao nao
    cobriu. Com o gate de cobertura em vigor esse trecho e de poucos metros, e a
    velocidade nao muda de forma relevante em poucos metros -- mas *achatar* o
    tempo ali muda, e muito.
    """
    uncovered = float(wrap_position) - float(positions[-1])
    if uncovered <= 0.0:
        return float(elapsed[-1])
    step_distance = float(positions[-1] - positions[-2])
    step_time = float(elapsed[-1] - elapsed[-2])
    if step_distance <= 1e-6 or step_time <= 1e-9:
        return float(elapsed[-1])
    return float(elapsed[-1] + uncovered * step_time / step_distance)


def resample_lap(
    frame: pd.DataFrame,
    track: TrackGeometry,
    channels: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Volta alinhada -> volta na grade da pista, com `track.size` linhas.

    Exige as colunas que `align_lap` produz. O indice do resultado e o indice da
    grade, entao `frame.loc[i]` e o mesmo ponto de pista em todas as voltas.
    """
    for required in ("s_unwrapped", "lateral", "elapsed_s"):
        if required not in frame.columns:
            raise ValueError(f"volta nao alinhada: falta a coluna `{required}`")
    if len(frame) < 4:
        raise ValueError("volta curta demais para reamostrar")

    positions = frame["s_unwrapped"].to_numpy(dtype=float)
    # `np.interp` exige eixo crescente. Um trecho andando para tras (piao,
    # tomada de rumo no box) e raro e curto; forcar a monotonia congela a volta
    # naquele metro em vez de embaralhar toda a interpolacao.
    positions = np.maximum.accumulate(positions)

    start = float(positions[0])
    # Cada ponto da grade vira a distancia equivalente dentro da faixa coberta
    # pela volta, o que fecha o laco na linha de chegada.
    grid_targets = start + np.mod(track.s - start, track.length)
    wrap_position = start + track.length

    if channels is None:
        channels = [
            column
            for column in frame.columns
            if column not in DROPPED_CHANNELS and pd.api.types.is_numeric_dtype(frame[column])
        ]

    data: Dict[str, np.ndarray] = {
        "s": track.s.copy(),
        "curvature": track.curvature.copy(),
        "width_left": track.width_left.copy(),
        "width_right": track.width_right.copy(),
        "elevation": track.elevation.copy(),
    }

    for channel in channels:
        values = frame[channel].to_numpy(dtype=float)
        finite = np.isfinite(values)
        if finite.sum() < 2:
            data[channel] = np.full(track.size, np.nan)
            continue
        sub_positions, sub_values = positions[finite], values[finite]

        if channel in ANGULAR_CHANNELS:
            # Desenrola antes de interpolar e reenrola depois: a media entre
            # -3,14 e +3,14 e 0, que aponta para o lado oposto do certo.
            unwrapped = np.unwrap(sub_values)
            # No fechamento o angulo continua girando no mesmo sentido; qual
            # sentido depende de a pista ser horaria ou anti-horaria, entao ele
            # sai da propria volta em vez de ser assumido.
            continuation = float(unwrapped[-1] + (unwrapped[-1] - unwrapped[-2]))
            resampled = _interp_circular(
                grid_targets, sub_positions, unwrapped, continuation, wrap_position
            )
            data[channel] = np.arctan2(np.sin(resampled), np.cos(resampled))
        elif channel in DISCRETE_CHANNELS:
            index = np.searchsorted(sub_positions, grid_targets, side="right") - 1
            data[channel] = sub_values[np.clip(index, 0, sub_values.size - 1)]
        elif channel == "elapsed_s":
            # O tempo nao fecha o laco: ele cresce ate o fim da volta. E o valor
            # no ponto de fechamento nao e o da ultima amostra -- se fosse, o
            # trecho entre a ultima amostra e a linha ficaria com tempo
            # constante, ou seja, velocidade infinita.
            #
            # Medido: a volta `2026-06-19_23-24-46#0005` termina 16 m antes da
            # linha, e com o tempo achatado nesses 16 m o ultimo microsetor
            # saia em 0,719 s -- 360 km/h numa reta onde o carro fazia 271, e
            # entrava como recorde na referencia do piloto.
            #
            # O fechamento e extrapolado pela ultima velocidade observada, que e
            # a unica informacao que a volta tem sobre o trecho que nao gravou.
            data[channel] = _interp_circular(
                grid_targets,
                sub_positions,
                sub_values,
                _closing_time(sub_positions, sub_values, wrap_position),
                wrap_position,
            )
        else:
            data[channel] = _interp_circular(
                grid_targets, sub_positions, sub_values, float(sub_values[0]), wrap_position
            )

    resampled = pd.DataFrame(data)
    if "elapsed_s" in resampled.columns:
        elapsed, total = _reference_clock_to_grid(resampled["elapsed_s"].to_numpy(dtype=float))
        resampled["elapsed_s"] = elapsed
        resampled["lap_time_s"] = total
    resampled.index.name = "grid_index"
    return resampled


def _reference_clock_to_grid(elapsed: np.ndarray) -> tuple:
    """Zera o relogio na origem da grade, e nao onde a volta comecou.

    Sem isto o tempo acumulado nao e monotonico ao longo da grade, e o motivo e
    geometrico: a volta comeca alguns metros depois da linha (a primeira amostra
    cai em s = 3,17 m numa volta medida), enquanto a grade comeca em s = 0. Os
    dois ou tres primeiros pontos da grade sao, portanto, o *fim* da volta -- o
    vetor sai como [84,83, 84,85, 0,01, 0,04, ...].

    Uma diferenca de tempos calculada sobre isso da o tempo do microsetor errado
    exatamente no primeiro deles, e um passo negativo de -84 s no ponto da
    virada. Re-referenciar resolve de vez: toda volta passa a comecar em s = 0,
    que e o mesmo lugar em todas elas.

    O total inclui o passo que fecha o laco, extrapolado do ultimo passo real --
    sao ~2 m que nenhuma amostra cobre porque a volta e cortada na linha.
    """
    if elapsed.size < 3:
        return elapsed - elapsed[0], float(np.nanmax(elapsed) - np.nanmin(elapsed))
    span = float(np.nanmax(elapsed) - np.nanmin(elapsed))
    shifted = np.mod(elapsed - elapsed[0], span) if span > 0 else elapsed - elapsed[0]
    shifted = np.maximum.accumulate(shifted)
    closing = float(shifted[-1] - shifted[-2])
    return shifted, float(shifted[-1] + closing)


def lap_time_from_grid(resampled: pd.DataFrame) -> float:
    """Tempo da volta lido da propria volta reamostrada."""
    if "lap_time_s" in resampled.columns:
        return float(resampled["lap_time_s"].iloc[0])
    elapsed = resampled["elapsed_s"].to_numpy(dtype=float)
    return float(np.nanmax(elapsed) - np.nanmin(elapsed))


def speed_from_time(resampled: pd.DataFrame, track: TrackGeometry) -> np.ndarray:
    """Velocidade implicita no tempo acumulado, em km/h.

    Serve de conferencia contra o canal `speed_kmh`: se as duas discordam muito,
    ou o alinhamento escorregou ou a gravacao tem buraco.

    O passo usado e o da **trajetoria** e nao o da grade. Sao coisas diferentes:
    numa curva a linha por fora percorre mais que os 2 m de centerline entre
    dois pontos da grade, e usar 2 m ali subestima a velocidade justamente onde
    ela mais varia.
    """
    from ..track.trajectory import step_lengths

    elapsed = resampled["elapsed_s"].to_numpy(dtype=float)
    dt = np.diff(elapsed, append=elapsed[-1] + (elapsed[-1] - elapsed[-2]))
    distance = (
        step_lengths(track, resampled["lateral"].to_numpy(dtype=float))
        if "lateral" in resampled.columns
        else np.full(track.size, track.step)
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        speed = np.where(dt > 1e-6, distance / dt, np.nan)
    return speed * 3.6
