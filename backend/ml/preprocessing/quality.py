"""O que faz uma volta poder entrar no dataset.

Cada gate aqui existe por causa de uma volta concreta do dataset que passaria
sem ele:

* **amostragem** — as duas voltas "mais rapidas" das gravacoes sao 82,698 s e
  83,469 s, ambas gravadas a 7,6 Hz. Sao gravacoes truncadas reportando tempo
  menor, e sem este gate elas viram o alvo que o modelo persegue.
* **carro parado** — a sessao `2026-08-16_03-30-14` tem uma volta de 713
  amostras com velocidade mediana zero: o carro no box.
* **cobertura** — voltas interrompidas no meio da gravacao cobrem meia pista e
  ainda assim tem tempo plausivel. E mesmo perto do fim importa: 16 m sem
  gravacao antes da linha viravam um microsetor de 0,719 s.
* **buracos** — 178 das 242 voltas com cobertura tem pelo menos um intervalo
  acima de 0,5 s entre amostras; a 200 km/h, meio segundo e 28 m de trajetoria
  que a interpolacao inventa.
* **fora de pista** — uma volta com duas rodas na grama nao ensina traçado.
* **canais de pilotagem** — a sessao `2026-06-14_12-23-46` gravou 12 voltas
  limpas, com posicao e velocidade perfeitas e **nenhum** bloco `carPhysics`:
  sem acelerador, sem freio, sem pneu. Elas passavam por todos os outros gates,
  entravam no dataset, e nove delas caiam no conjunto de teste -- que assim
  media a rede num conjunto em que o alvo nao existe.

Nada aqui conserta volta. O gate diz sim ou nao e diz por que.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .. import config
from ..track.geometry import TrackGeometry
from .alignment import AlignmentReport
from .cleaning import sample_gaps, sample_rate_hz, stopped_fraction


@dataclass
class LapQuality:
    """Veredito sobre uma volta, com os numeros que o produziram."""

    valid: bool
    reasons: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {"valid": self.valid, "reasons": list(self.reasons), "metrics": dict(self.metrics)}


def _off_track_fraction(frame: pd.DataFrame) -> float:
    if "off_track" in frame.columns and frame["off_track"].notna().any():
        return float(frame["off_track"].astype(bool).mean())
    if "tyres_out" in frame.columns and frame["tyres_out"].notna().any():
        # Duas rodas fora ja e limite de pista excedido nos regulamentos que o
        # jogo aplica; uma roda e uso de zebra.
        return float((frame["tyres_out"].fillna(0) >= 2).mean())
    return 0.0


def _outside_corridor_fraction(frame: pd.DataFrame, track: TrackGeometry) -> float:
    """Fracao de amostras cujo centro do carro esta fora do corredor util.

    Existe porque `off_track` vem da memoria compartilhada e nem toda gravacao a
    tem. Medida na volta limpa de referencia: 4,7%, que e uso de zebra.
    """
    if "lateral" not in frame.columns or "s" not in frame.columns:
        return 0.0
    low, high = track.corridor()
    index = track.index_of(frame["s"].to_numpy(dtype=float))
    lateral = frame["lateral"].to_numpy(dtype=float)
    return float(np.mean((lateral < low[index]) | (lateral > high[index])))


def _channel_coverage(frame: pd.DataFrame, channels: Sequence[str]) -> Dict[str, float]:
    """Fracao de amostras em que cada canal tem valor."""
    return {
        channel: float(frame[channel].notna().mean()) if channel in frame.columns else 0.0
        for channel in channels
    }


def evaluate_lap(
    frame: pd.DataFrame,
    track: TrackGeometry,
    alignment: Optional[AlignmentReport] = None,
    gates: config.LapQualityGates = config.DEFAULT_GATES,
) -> LapQuality:
    """Aplica os gates a uma volta ja limpa e alinhada."""
    reasons: List[str] = []
    metrics: Dict[str, float] = {}

    if frame.empty:
        return LapQuality(False, ["volta vazia"], metrics)

    coverage = _channel_coverage(frame, config.REQUIRED_CHANNELS)
    for channel, present in sorted(coverage.items()):
        metrics[f"coverage_{channel}"] = present
    missing = [
        channel
        for channel, present in sorted(coverage.items())
        if present < gates.min_channel_coverage
    ]
    if missing:
        reasons.append(f"canais ausentes: {', '.join(missing)}")

    hz = sample_rate_hz(frame)
    max_gap, long_gaps = sample_gaps(frame, gates.max_sample_gap_s)
    stopped = stopped_fraction(frame)
    off_track = _off_track_fraction(frame)
    outside = _outside_corridor_fraction(frame, track)

    elapsed = frame["elapsed_s"].to_numpy(dtype=float) if "elapsed_s" in frame.columns else None
    duration = float(np.nanmax(elapsed) - np.nanmin(elapsed)) if elapsed is not None else float("nan")

    metrics.update(
        {
            "sample_count": float(len(frame)),
            "sample_hz": hz,
            "duration_s": duration,
            "max_gap_s": max_gap,
            "long_gaps": float(long_gaps),
            "stopped_fraction": stopped,
            "off_track_fraction": off_track,
            "outside_corridor_fraction": outside,
        }
    )
    if "speed_kmh" in frame.columns:
        speed = frame["speed_kmh"].to_numpy(dtype=float)
        metrics["speed_mean_kmh"] = float(np.nanmean(speed))
        metrics["speed_max_kmh"] = float(np.nanmax(speed))
        metrics["speed_min_kmh"] = float(np.nanmin(speed))
    if alignment is not None:
        metrics.update(alignment.to_dict())

    if not np.isfinite(duration):
        reasons.append("sem tempo utilizavel")
    elif duration < gates.min_lap_seconds:
        reasons.append(f"volta curta demais ({duration:.1f}s < {gates.min_lap_seconds:.0f}s)")
    elif duration > gates.max_lap_seconds:
        reasons.append(f"volta longa demais ({duration:.1f}s > {gates.max_lap_seconds:.0f}s)")

    if hz < gates.min_sample_hz:
        reasons.append(f"amostragem baixa ({hz:.1f} Hz < {gates.min_sample_hz:.0f} Hz)")
    elif hz > gates.max_sample_hz:
        reasons.append(f"amostragem implausivel ({hz:.1f} Hz)")

    if alignment is not None:
        uncovered = (1.0 - alignment.coverage) * track.length
        metrics["uncovered_m"] = uncovered
        if uncovered > gates.max_uncovered_m:
            reasons.append(
                f"faltam {uncovered:.1f} m de pista (limite {gates.max_uncovered_m:.0f} m)"
            )

    if long_gaps > gates.max_long_gaps:
        reasons.append(f"{long_gaps} buracos acima de {gates.max_sample_gap_s:.1f}s")

    if stopped > gates.max_stopped_fraction:
        reasons.append(f"carro parado em {stopped:.1%} das amostras")

    if off_track > gates.max_off_track_fraction:
        reasons.append(f"fora de pista em {off_track:.1%} das amostras")

    return LapQuality(valid=not reasons, reasons=reasons, metrics=metrics)
