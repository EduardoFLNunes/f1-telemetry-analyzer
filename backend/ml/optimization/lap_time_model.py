"""Tempo de volta de uma trajetoria, por simulacao quase-estacionaria.

O algoritmo evolutivo precisa comparar trajetorias que ninguem dirigiu. Nao da
para medir o tempo delas -- tem de ser estimado, e estimado por fisica, porque
uma rede treinada nas voltas do piloto so sabe premiar o que ela ja viu e nunca
apontaria nada melhor que a melhor volta dele.

O metodo e o classico de tres passagens:

1. **limite de curva** — em cada ponto, `v = sqrt(a_lat / k)` com o `a_lat` que
   o envelope medido concede naquela velocidade;
2. **passagem para tras** — a partir de cada minimo, propaga para tras o quanto
   o carro consegue frear chegando ali;
3. **passagem para frente** — propaga para frente o quanto ele consegue acelerar
   saindo dali.

As duas ultimas usam a elipse de atrito: numa curva de 3 g quase nao sobra pneu
para acelerar, e ignorar isso produz voltas simuladas impossiveis.

As passagens sao sequenciais ponto a ponto -- nao ha como vetorizar ao longo da
pista, porque a velocidade em cada ponto depende do anterior. O que se vetoriza
e a **populacao**: os 8668 passos de uma geracao rodam com todos os individuos
dentro do mesmo array. Individuo a individuo, uma geracao levava minutos.

O que o modelo **nao** tem: transferencia de carga, mapa de motor por marcha,
degradacao de pneu, vento, e o proprio piloto. Ele nao serve para prever o tempo
absoluto de uma volta -- serve para dizer se a trajetoria A e mais rapida que a
B, que e a pergunta do algoritmo evolutivo. O erro contra as voltas reais e
medido por `calibration_error`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from .. import config
from ..track.geometry import TrackGeometry
from ..track.trajectory import curvature as trajectory_curvature
from ..track.trajectory import step_lengths
from .vehicle_model import VehicleEnvelope

# Piso de velocidade da simulacao. Sem ele, uma curvatura absurda vinda de uma
# trajetoria degenerada produz v = 0 e tempo infinito, o que quebra a selecao em
# vez de so pontuar mal.
MIN_SPEED_MPS = 5.0


@dataclass
class LapTimeResult:
    """Tempo estimado e o perfil que o produziu."""

    lap_time_s: float
    speed_mps: np.ndarray
    cornering_limit_mps: np.ndarray
    step_time_s: np.ndarray
    step_length_m: np.ndarray
    path_length_m: float

    @property
    def speed_kmh(self) -> np.ndarray:
        return self.speed_mps * 3.6

    def cumulative_time(self) -> np.ndarray:
        return np.concatenate([[0.0], np.cumsum(self.step_time_s)[:-1]])


def prepare(
    track: TrackGeometry,
    laterals: np.ndarray,
    smoothing_m: float = config.SIMULATION_CURVATURE_SMOOTHING_M,
) -> Tuple[np.ndarray, np.ndarray]:
    """(curvatura, comprimento de passo) de cada trajetoria, ambos (n, grade).

    A curvatura sai com a janela do simulador (30 m) e nao com a da geometria
    (12 m). Sao perguntas diferentes: a segunda descreve a pista, a primeira
    descreve o raio que o carro efetivamente percorre.
    """
    batch = np.atleast_2d(np.asarray(laterals, dtype=float))
    curvature = np.vstack(
        [trajectory_curvature(track, row, smoothing_m=smoothing_m) for row in batch]
    )
    lengths = np.vstack([step_lengths(track, row) for row in batch])
    return curvature, lengths


def solve_speed(
    curvature: np.ndarray,
    lengths: np.ndarray,
    envelope: VehicleEnvelope,
    passes: int = 2,
) -> np.ndarray:
    """Perfil de velocidade de cada trajetoria. Entra (n, grade), sai (n, grade).

    `passes` e quantas vezes as passagens para tras e para frente se repetem. A
    pista e fechada: a velocidade no ponto 0 depende do que veio antes dele, que
    e o fim da volta. Uma passagem ja converge quase sempre e duas fecham o laco
    em todos os casos medidos.
    """
    curvature = np.abs(np.atleast_2d(curvature))
    lengths = np.atleast_2d(lengths)
    size = curvature.shape[1]

    speed = np.maximum(envelope.cornering_speed(curvature), MIN_SPEED_MPS)

    for _ in range(max(1, passes)):
        for offset in range(size):
            i = (size - 1 - offset) % size
            nxt = (i + 1) % size
            lateral_used = speed[:, i] ** 2 * curvature[:, i]
            decel = envelope.longitudinal_available(speed[:, i], lateral_used, braking=True)
            reachable = np.sqrt(np.maximum(speed[:, nxt] ** 2 + 2.0 * decel * lengths[:, i], 0.0))
            speed[:, i] = np.maximum(np.minimum(speed[:, i], reachable), MIN_SPEED_MPS)

        for i in range(size):
            nxt = (i + 1) % size
            lateral_used = speed[:, i] ** 2 * curvature[:, i]
            accel = envelope.longitudinal_available(speed[:, i], lateral_used, braking=False)
            reachable = np.sqrt(np.maximum(speed[:, i] ** 2 + 2.0 * accel * lengths[:, i], 0.0))
            speed[:, nxt] = np.maximum(np.minimum(speed[:, nxt], reachable), MIN_SPEED_MPS)

    return np.minimum(speed, envelope.top_speed_mps)


def step_times(speed: np.ndarray, lengths: np.ndarray) -> np.ndarray:
    """Tempo de cada passo, pela velocidade media do trecho.

    Media entre as pontas e nao a velocidade do ponto: com passo de 2 m e
    variacao de ate 1 m/s por passo, usar a do ponto vies o tempo sempre para o
    mesmo lado.
    """
    average = 0.5 * (speed + np.roll(speed, -1, axis=-1))
    return lengths / np.maximum(average, MIN_SPEED_MPS)


def simulate_batch(
    track: TrackGeometry,
    laterals: np.ndarray,
    envelope: VehicleEnvelope,
    passes: int = 2,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(tempos, velocidades, tempos por passo) de uma populacao inteira."""
    curvature, lengths = prepare(track, laterals)
    speed = solve_speed(curvature, lengths, envelope, passes)
    per_step = step_times(speed, lengths)
    return per_step.sum(axis=1), speed, per_step


def simulate(
    track: TrackGeometry,
    lateral: np.ndarray,
    envelope: VehicleEnvelope,
    passes: int = 2,
) -> LapTimeResult:
    """Uma trajetoria so, com o detalhe todo."""
    curvature, lengths = prepare(track, lateral)
    speed = solve_speed(curvature, lengths, envelope, passes)
    per_step = step_times(speed, lengths)
    return LapTimeResult(
        lap_time_s=float(per_step[0].sum()),
        speed_mps=speed[0],
        cornering_limit_mps=np.maximum(
            envelope.cornering_speed(np.abs(curvature[0])), MIN_SPEED_MPS
        ),
        step_time_s=per_step[0],
        step_length_m=lengths[0],
        path_length_m=float(lengths[0].sum()),
    )


def calibration_error(
    track: TrackGeometry,
    envelope: VehicleEnvelope,
    laterals: np.ndarray,
    measured_times: np.ndarray,
) -> dict:
    """Compara o tempo simulado com o tempo real das mesmas trajetorias.

    O numero que interessa nao e o erro medio -- um vies constante nao muda
    nenhuma decisao do algoritmo evolutivo, que so compara trajetorias entre si.
    O que interessa e a correlacao entre simulado e medido: e ela que diz se o
    modelo ordena as trajetorias do mesmo jeito que a pista ordena.
    """
    simulated, _, _ = simulate_batch(track, laterals, envelope)
    measured = np.asarray(measured_times, dtype=float)
    residual = simulated - measured
    correlation = (
        float(np.corrcoef(simulated, measured)[0, 1]) if simulated.size > 2 else float("nan")
    )
    return {
        "laps": int(simulated.size),
        "mean_simulated_s": float(simulated.mean()),
        "mean_measured_s": float(measured.mean()),
        "bias_s": float(residual.mean()),
        "mae_s": float(np.abs(residual).mean()),
        "std_residual_s": float(residual.std()),
        "correlation": correlation,
    }
