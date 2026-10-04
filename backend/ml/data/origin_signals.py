"""Sinais candidatos para separar volta da IA de volta do piloto (ADR 0014).

As gravacoes antigas nao dizem quem pilotou. Antes de treinar qualquer
detector, que precisa de sessoes novas rotuladas, este modulo so mede, volta a
volta, coisas em que a IA do jogo e uma pessoa tendem a diferir:

* volante: quao rapido ele gira e quantas vezes muda de sentido por km;
* pedais: quanto tempo o acelerador e o freio passam em valores parciais, o
  pico de cada frenagem e quanto tempo o freio leva para chegar nele;
* trocas de marcha: o RPM em que cada marcha sobe, e quanto ele varia;
* (por sessao, fora daqui) a dispersao do ponto de frenagem e do apice entre
  voltas, e a do tempo de volta.

Nenhum destes numeros e um rotulo. Eles so viram detector quando houver voltas
com `origem` conhecida para calibrar.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

# Abaixo disto o pedal esta solto; acima do complemento, no fundo.
PEDAL_PARTIAL_LOW = 0.05
PEDAL_PARTIAL_HIGH = 0.95
# Mudanca minima do volante para contar como mudanca de sentido. Medido: numa
# volta de 2026-08-19 o volante vai de -0,52 a +0,73; 0,01 e ~1 % disso.
STEERING_REVERSAL = 0.01
# Inicio de frenagem: o mesmo limiar da Fase 2b (`empirical.BRAKE_ONSET`).
BRAKE_ON = 0.15


def _time_weights(time_s: np.ndarray) -> np.ndarray:
    dt = np.diff(time_s, append=time_s[-1])
    return np.clip(np.nan_to_num(dt), 0.0, 1.0)


def steering_reversals(steering: np.ndarray, threshold: float = STEERING_REVERSAL) -> int:
    """Mudancas de sentido do volante maiores que `threshold` (com histerese)."""
    values = steering[np.isfinite(steering)]
    if values.size < 3:
        return 0
    count, direction = 0, 0
    low = high = extreme = values[0]
    for value in values[1:]:
        if direction == 0:
            low, high = min(low, value), max(high, value)
            if value - low > threshold:
                direction, extreme = 1, value
            elif high - value > threshold:
                direction, extreme = -1, value
        elif direction == 1:
            if value > extreme:
                extreme = value
            elif extreme - value > threshold:
                count, direction, extreme = count + 1, -1, value
        else:
            if value < extreme:
                extreme = value
            elif value - extreme > threshold:
                count, direction, extreme = count + 1, 1, value
    return count


def lap_signals(aligned: pd.DataFrame, track_length: float) -> Dict[str, float]:
    """Sinais de uma volta limpa e alinhada (amostras no tempo, nao na grade)."""
    time_s = aligned["elapsed_s"].to_numpy(dtype=float)
    weights = _time_weights(time_s)
    total = float(weights.sum()) or float("nan")
    out: Dict[str, float] = {}

    steering = aligned["steering"].to_numpy(dtype=float) if "steering" in aligned else np.full(len(aligned), np.nan)
    dt = np.diff(time_s)
    with np.errstate(divide="ignore", invalid="ignore"):
        rate = np.abs(np.diff(steering)) / dt
    rate = rate[np.isfinite(rate) & (dt > 1e-4)]
    out["volante_taxa_p95"] = float(np.percentile(rate, 95)) if rate.size else float("nan")
    out["volante_reversoes_km"] = steering_reversals(steering) / (track_length / 1000.0)

    for pedal in ("throttle", "brake"):
        values = aligned[pedal].to_numpy(dtype=float) if pedal in aligned else np.full(len(aligned), np.nan)
        partial = (values > PEDAL_PARTIAL_LOW) & (values < PEDAL_PARTIAL_HIGH)
        name = "acelerador" if pedal == "throttle" else "freio"
        out[f"{name}_parcial"] = float(weights[partial].sum() / total) if total == total else float("nan")

    brake = np.nan_to_num(aligned["brake"].to_numpy(dtype=float)) if "brake" in aligned else np.zeros(len(aligned))
    on = brake >= BRAKE_ON
    starts = np.flatnonzero(on & ~np.r_[False, on[:-1]])
    ends = np.flatnonzero(on & ~np.r_[on[1:], False])
    peaks, rises = [], []
    for start, end in zip(starts, ends):
        segment = brake[start : end + 1]
        peak = float(segment.max())
        peaks.append(peak)
        reach = start + int(np.argmax(segment >= 0.9 * peak))
        rises.append(float(time_s[reach] - time_s[start]))
    out["freio_eventos"] = float(len(peaks))
    out["freio_pico_mediano"] = float(np.median(peaks)) if peaks else float("nan")
    out["freio_subida_s"] = float(np.median(rises)) if rises else float("nan")

    gear = aligned["gear"].to_numpy(dtype=float) if "gear" in aligned else np.full(len(aligned), np.nan)
    rpm = aligned["rpm"].to_numpy(dtype=float) if "rpm" in aligned else np.full(len(aligned), np.nan)
    # RPM na ultima amostra antes de a marcha subir. No Assetto Corsa 0 e re e
    # 1 e neutro: sair do neutro nao e troca de marcha.
    up = np.flatnonzero((np.diff(gear) > 0) & (gear[:-1] >= 2))
    shift_rpm = rpm[up]
    shift_rpm = shift_rpm[np.isfinite(shift_rpm)]
    out["troca_rpm_mediana"] = float(np.median(shift_rpm)) if shift_rpm.size else float("nan")
    out["troca_rpm_dp"] = (
        float(1.4826 * np.median(np.abs(shift_rpm - np.median(shift_rpm)))) if shift_rpm.size > 2 else float("nan")
    )
    return out
