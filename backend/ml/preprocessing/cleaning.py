"""Limpeza de uma volta crua, antes de qualquer alinhamento.

Tudo aqui e conservador de proposito: corrige o que e comprovadamente formato
(escala de porcentagem, ordem temporal, duplicata de quadro) e **nao** tenta
consertar pilotagem. Uma volta ruim tem de continuar ruim ate o gate de
qualidade decidir o que fazer com ela -- suavizar telemetria antes de julgar a
volta e o caminho mais curto para um dataset que so contem voltas medianas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np
import pandas as pd

from .. import config

# Colunas sem as quais a amostra nao serve para nada: sem posicao nao ha
# projecao, e sem tempo nao ha ordem.
REQUIRED_COLUMNS = ("x", "z", "timestamp_s")

# Canais que sao fracao de 0 a 1 no formato do jogo.
UNIT_CHANNELS = ("throttle", "brake", "clutch")

# Canais que so fazem sentido dentro de uma faixa fisica. Fora dela e leitura
# corrompida da memoria compartilhada, e nao manobra.
PHYSICAL_LIMITS = {
    "speed_kmh": (0.0, 450.0),
    "steering": (-1.5, 1.5),
    "gear": (-1.0, 10.0),
    "rpm": (0.0, 25_000.0),
    "lateral_g": (-8.0, 8.0),
    "longitudinal_g": (-8.0, 8.0),
    "vertical_g": (-8.0, 8.0),
    "heading": (-np.pi, np.pi),
}


@dataclass
class CleaningReport:
    """O que a limpeza tirou. Vai junto com a volta ate o inventario."""

    input_rows: int = 0
    output_rows: int = 0
    dropped_missing: int = 0
    dropped_duplicate_time: int = 0
    reordered: int = 0
    clipped: Dict[str, int] = field(default_factory=dict)
    rescaled: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "input_rows": self.input_rows,
            "output_rows": self.output_rows,
            "dropped_missing": self.dropped_missing,
            "dropped_duplicate_time": self.dropped_duplicate_time,
            "reordered": self.reordered,
            "clipped": dict(self.clipped),
            "rescaled": list(self.rescaled),
        }


def clean_lap(frame: pd.DataFrame) -> tuple:
    """Devolve (frame limpo, relatorio)."""
    report = CleaningReport(input_rows=int(len(frame)))
    if frame.empty:
        return frame.copy(), report

    out = frame.copy()
    for column in out.columns:
        if column not in ("off_track",):
            out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.replace([np.inf, -np.inf], np.nan)

    present = [c for c in REQUIRED_COLUMNS if c in out.columns]
    before = len(out)
    out = out.dropna(subset=present)
    report.dropped_missing = before - len(out)

    # O gravador escreve em ordem, mas quadros repetidos aparecem quando a
    # amostragem adaptativa do runtime muda de frequencia.
    if "timestamp_s" in out.columns:
        if not out["timestamp_s"].is_monotonic_increasing:
            report.reordered = int((out["timestamp_s"].diff() < 0).sum())
            out = out.sort_values("timestamp_s", kind="stable")
        before = len(out)
        out = out.drop_duplicates(subset="timestamp_s", keep="first")
        report.dropped_duplicate_time = before - len(out)

    for channel in UNIT_CHANNELS:
        if channel not in out.columns:
            continue
        values = out[channel]
        peak = values.max(skipna=True)
        if pd.notna(peak) and peak > 1.5:
            # Algumas versoes do exportador mandam 0-100 em vez de 0-1.
            out[channel] = values / 100.0
            report.rescaled.append(channel)
        out[channel] = out[channel].clip(0.0, 1.0)

    for channel, (low, high) in PHYSICAL_LIMITS.items():
        if channel not in out.columns:
            continue
        values = out[channel]
        outside = int(((values < low) | (values > high)).sum())
        if outside:
            report.clipped[channel] = outside
            out[channel] = values.clip(low, high)

    if "off_track" in out.columns:
        out["off_track"] = out["off_track"].fillna(False).astype(bool)

    report.output_rows = int(len(out))
    return out.reset_index(drop=True), report


def stopped_fraction(frame: pd.DataFrame) -> float:
    """Fracao de amostras com o carro parado.

    Serve para pegar box, spin e reset de sessao. Medido: a sessao
    `2026-08-16_03-30-14` tem uma "volta" de 713 amostras com velocidade
    mediana zero, parada a 24 m da centerline -- e o carro no box, e sem esse
    filtro ela entra no dataset como trajetoria.
    """
    if "speed_kmh" not in frame.columns or frame.empty:
        return 0.0
    return float((frame["speed_kmh"] < config.STOPPED_SPEED_KMH).mean())


def sample_gaps(frame: pd.DataFrame, threshold: float = config.MAX_SAMPLE_GAP_S) -> tuple:
    """(maior intervalo entre amostras, quantos passaram do limite)."""
    if "timestamp_s" not in frame.columns or len(frame) < 2:
        return 0.0, 0
    deltas = frame["timestamp_s"].diff().dropna()
    if deltas.empty:
        return 0.0, 0
    return float(deltas.max()), int((deltas > threshold).sum())


def sample_rate_hz(frame: pd.DataFrame) -> float:
    """Frequencia efetiva de amostragem da volta.

    Calculada pelo relogio de parede e nao pelo numero nominal do gravador: o
    runtime usa amostragem adaptativa e cai de 60 para 20 Hz sob carga, o que
    nao aparece em lugar nenhum da configuracao.
    """
    if "timestamp_s" not in frame.columns or len(frame) < 2:
        return 0.0
    span = float(frame["timestamp_s"].iloc[-1] - frame["timestamp_s"].iloc[0])
    return float(len(frame) - 1) / span if span > 0 else 0.0
