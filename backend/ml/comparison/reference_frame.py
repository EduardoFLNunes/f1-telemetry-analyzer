"""Da trajetoria otimizada para uma "volta" comparavel com a do jogador.

O algoritmo evolutivo devolve uma trajetoria -- so a forma da linha. Comparar
uma volta do jogador com ela exige mais do que isso: exige velocidade, pedais e
tempo acumulado em cada ponto, que e o que a volta do jogador tem.

A velocidade sai da simulacao fisica sobre a propria trajetoria, e o tempo, da
integral dela. Os pedais sao **derivados do perfil de velocidade**, e nao
inventados: onde o perfil desacelera mais do que o arrasto explicaria, o carro
esta freando, e a intensidade e a fracao do limite de frenagem que aquela
desaceleracao consome. E uma leitura da fisica, nao um palpite de pilotagem --
e a comparacao com o pedal do jogador continua valendo porque as duas coisas
sao medidas na mesma unidade: fracao do que o carro aguenta.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ..optimization.lap_time_model import LapTimeResult, simulate
from ..optimization.vehicle_model import VehicleEnvelope
from ..track.geometry import TrackGeometry


def pedals_from_speed(
    track: TrackGeometry,
    result: LapTimeResult,
    envelope: VehicleEnvelope,
    curvature: Optional[np.ndarray] = None,
) -> tuple:
    """(freio, acelerador) implicitos num perfil de velocidade."""
    speed = result.speed_mps
    following = np.roll(speed, -1)
    # a = (v2^2 - v1^2) / (2*ds), a forma que nao precisa do tempo.
    acceleration = (following**2 - speed**2) / (2.0 * np.maximum(result.step_length_m, 1e-6))

    if curvature is None:
        curvature = np.zeros(track.size)
    lateral_used = speed**2 * np.abs(curvature)
    brake_capacity = envelope.longitudinal_available(speed, lateral_used, braking=True)
    drive_capacity = envelope.longitudinal_available(speed, lateral_used, braking=False)

    brake = np.clip(-acceleration / np.maximum(brake_capacity, 1e-6), 0.0, 1.0)
    throttle = np.clip(acceleration / np.maximum(drive_capacity, 1e-6), 0.0, 1.0)
    # Em velocidade estavel o carro nao esta nem freando nem acelerando de
    # verdade, mas o acelerador esta em algum lugar sustentando a velocidade.
    throttle = np.where((brake < 0.02) & (throttle < 0.02), 0.5, throttle)
    return brake, throttle


def reference_lap_frame(
    track: TrackGeometry,
    lateral: np.ndarray,
    envelope: VehicleEnvelope,
) -> pd.DataFrame:
    """Trajetoria -> volta de referencia, na grade da pista."""
    from ..track.trajectory import curvature as trajectory_curvature

    lateral = np.asarray(lateral, dtype=float)
    result = simulate(track, lateral, envelope)
    curvature = trajectory_curvature(track, lateral)
    brake, throttle = pedals_from_speed(track, result, envelope, curvature)

    frame = pd.DataFrame(
        {
            "s": track.s,
            "lateral": lateral,
            "speed_kmh": result.speed_kmh,
            "brake": brake,
            "throttle": throttle,
            "elapsed_s": result.cumulative_time(),
            "path_curvature": curvature,
            "step_length_m": result.step_length_m,
        }
    )
    frame["lap_time_s"] = result.lap_time_s
    return frame


def rescale_to_measured(frame: pd.DataFrame, measured_lap_time: float) -> pd.DataFrame:
    """Reescala o relogio da referencia para um tempo de volta medido.

    O simulador quase-estacionario tem vies conhecido -- ele e conservador, e em
    Interlagos entrega ~7,5% a mais que o cronometro. Esse vies nao atrapalha o
    algoritmo evolutivo, que so compara trajetorias entre si, mas atrapalha a
    comparacao com o jogador: um delta acumulado que termina em +6 s so porque o
    modelo e lento nao diz nada sobre a pilotagem.

    Reescalar preserva o **formato** do delta -- onde ele sobe e onde ele desce,
    que e o que se le no grafico -- e tira o vies constante.
    """
    out = frame.copy()
    simulated = float(out["lap_time_s"].iloc[0])
    if simulated <= 0:
        return out
    factor = float(measured_lap_time) / simulated
    out["elapsed_s"] = out["elapsed_s"] * factor
    out["lap_time_s"] = float(measured_lap_time)
    out["speed_kmh"] = out["speed_kmh"] / factor
    return out
